import asyncio
import aiohttp.web
import configparser
import os
import chess
import chess.syzygy
import chess.gaviota
import json


def static(url, path):
    # Workaround to serve a single static file.
    # TODO: https://github.com/KeepSafe/aiohttp/issues/468

    async def handler(request):
        prefix = url.rsplit("/", 1)[0] or "/"
        route = aiohttp.web.StaticRoute(None, prefix, os.path.dirname(__file__))

        request.match_info["filename"] = path
        return await route.handle(request)

    return handler


def jsonp(request, obj):
    json_str = json.dumps(obj, indent=2, sort_keys=True)

    callback = request.GET.get("callback")
    if callback:
        content = "%s(%s);" % (callback, json_str)
        return aiohttp.web.Response(text=content, content_type="application/javascript")
    else:
        return aiohttp.web.Response(text=json_str, content_type="text/json")


class Api(object):

    def __init__(self, config, loop):
        self.config = config
        self.loop = loop

        self.init_syzygy()
        self.init_gaviota()

    def init_syzygy(self):
        print("Loading syzygy tablebases ...")
        self.syzygy = chess.syzygy.Tablebases()

        for line in config.get("tablebases", "syzygy").splitlines():
            filename = line.strip()
            if not filename:
                continue

            num = self.syzygy.open_directory(filename)
            print("* Loaded %d syzygy tablebases from %r" % (num, filename))

    def init_gaviota(self):
        print("Loading gaviota tablebases ...")
        self.gaviota = chess.gaviota.open_tablebases()

        for line in config.get("tablebases", "gaviota").splitlines():
            filename = line.strip()
            if not filename:
                continue

            print("* Loaded gaviota tablebases from %r" % filename)

    def probe(self, board, load_root=False, load_wdl=False, load_dtz=False, load_dtm=False):
        result = {}

        if load_root:
            result["wdl"] = self.syzygy.probe_wdl(board)
            result["dtz"] = self.syzygy.probe_dtz(board)
            result["dtm"] = self.gaviota.probe_dtm(board)

        result["moves"] = {}

        for move in board.legal_moves:
            board.push(move)

            result["moves"][move.uci()] = move_info = {}

            if load_wdl:
                move_info["wdl"] = self.syzygy.probe_wdl(board)

            if load_dtz:
                move_info["dtz"] = self.syzygy.probe_dtz(board)

            if load_dtm:
                move_info["dtm"] = self.gaviota.probe_dtm(board)

            board.pop()

        return result

    async def probe_async(self, board, load_root=False, load_wdl=False, load_dtz=False, load_dtm=False):
        return await self.loop.run_in_executor(
            None,
            self.probe, board.copy(), load_root, load_wdl, load_dtz, load_dtm)

    def get_board(self, request):
        try:
            board = chess.Board(request.GET["fen"])
        except KeyError:
            raise aiohttp.web.HTTPBadRequest(reason="fen required")
        except ValueError:
            raise aiohttp.web.HTTPBadRequest(reason="invalid fen")

        if not board.is_valid():
            raise aiohttp.web.HTTPBadRequest(reason="illegal fen")

        return board

    async def v1(self, request):
        board = self.get_board(request)
        result = await self.probe_async(board, load_root=True, load_dtz=True)

        # Collapse move information to produce legacy API output.
        for move in result["moves"]:
            result["moves"][move] = result["moves"][move]["dtz"]

        return jsonp(request, result)

    async def v2(self, request):
        board = self.get_board(request)
        result = await self.probe_async(board, load_root=True, load_dtz=True, load_dtm=True)
        return jsonp(request, result)


async def init(config, loop):
    api = Api(config, loop)

    # Setup routes.
    app = aiohttp.web.Application(loop=loop)
    app.router.add_route("GET", "/favicon.ico", static("/favicon.ico", "favicon.ico"))
    app.router.add_route("GET", "/api/v1", api.v1)
    app.router.add_route("GET", "/api/v2", api.v2)

    # Create server.
    bind = config.get("server", "bind")
    port = config.getint("server", "port")
    server = await loop.create_server(app.make_handler(), bind, port)
    print("Listening on http://%s:%d/ ..." % (bind, port))
    return server


if __name__ == "__main__":
    loop = asyncio.get_event_loop()

    config = configparser.ConfigParser()

    config.read([
        os.path.join(os.path.dirname(__file__), "config.ini"),
        os.path.join(os.path.dirname(__file__), "config.default.ini"),
    ])

    try:
        loop.run_until_complete(init(config, loop))
        loop.run_forever()
    finally:
        loop.close()
