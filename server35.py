import aiohttp.web

import jinja2

import chess
import chess.syzygy
import chess.gaviota
import chess.pgn

import asyncio
import configparser
import os
import json
import logging
import random
import warnings

try:
    from htmlmin import minify as html_minify
except ImportError:
    warnings.warn("Not using HTML minification, htmlmin not imported.")

    def html_minify(html):
        return html


DEFAULT_FEN = "4k3/8/8/8/8/8/8/4K3 w - - 0 1"

EMPTY_FEN = "8/8/8/8/8/8/8/8 w - - 0 1"


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
        return aiohttp.web.Response(
            text=content,
            content_type="application/javascript")
    else:
        return aiohttp.web.Response(
            text=json_str,
            content_type="text/json")


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
            path = line.strip()
            if not path:
                continue

            num = self.syzygy.open_directory(path)
            print("* Loaded %d syzygy tablebases from %r" % (num, path))

    def init_gaviota(self):
        print("Loading gaviota tablebases ...")
        self.gaviota = chess.gaviota.open_tablebases()

        for line in config.get("tablebases", "gaviota").splitlines():
            path = line.strip()
            if not path:
                continue

            self.gaviota.open_directory(path)
            print("* Loaded gaviota tablebases from %r" % path)

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

    async def probe_async(self, board, *, load_root=False, load_wdl=False, load_dtz=False, load_dtm=False):
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

    async def pgn(self, request):
        board = chess.Board()

        game = chess.pgn.Game()
        node = game

        for _ in range(100):
            await self.probe_async(board, load_root=True, load_dtz=True)
            move = random.choice(list(board.legal_moves))
            node = node.add_variation(move)
            board.push(move)

        game.headers["Result"] = board.result()

        return aiohttp.web.Response(text=str(game))


class Frontend(object):

    def __init__(self, config, api, loop):
        self.config = config
        self.api = api
        self.loop = loop

        self.jinja = jinja2.Environment(
            loader=jinja2.FileSystemLoader("templates"))

    async def index(self, request):
        return "hello"

    async def apidoc(self, request):
        render = {}
        render["DEFAULT_FEN"] = DEFAULT_FEN
        render["status"] = 200

        # Pass the raw unchanged FEN.
        if "fen" in request.GET:
            render["fen"] = request.GET["fen"]

        try:
            board = chess.Board(request.GET["fen"])
        except KeyError:
            render["status"] = 400
            render["error"] = "fen required"
            render["sanitized_fen"] = EMPTY_FEN
        except ValueError:
            render["status"] = 400
            render["error"] = "invalid fen"
            render["sanitized_fen"] = EMPTY_FEN
        else:
            render["sanitized_fen"] = board.fen()

            if board.is_valid():
                result = await self.api.probe_async(board, load_root=True, load_dtz=True)
                render["request_body"] = json.dumps(result, indent=2, sort_keys=True)
            else:
                render["status"] = 400
                render["error"] = "illegal fen"

        template = self.jinja.get_template("apidoc.html")
        return aiohttp.web.Response(
            text=html_minify(template.render(render)),
            content_type="text/html")

    def legal(self, request):
        template = self.jinja.get_template("legal.html")
        return aiohttp.web.Response(
            text=html_minify(template.render()),
            content_type="text/html")

    def sitemap(self, request):
        entries = [
            "",
            "?fen=6N1/5KR1/2n5/8/8/8/2n5/1k6%20w%20-%20-%200%201",
            "?fen=4r3/1K6/8/8/5p2/3k4/8/7Q%20b%20-%20-%200%201",
            "apidoc?fen=6N1/5KR1/2n5/8/8/8/2n5/1k6%20w%20-%20-%200%201",
            "legal",
        ]

        base_url = self.config.get("server", "base_url")

        content = "\n".join(base_url + entry for entry in entries)
        return aiohttp.web.Response(text=content)


async def init(config, loop):
    print("---")

    api = Api(config, loop)
    frontend = Frontend(config, api, loop)

    # Check configured base url.
    assert config.get("server", "base_url").startswith("http")
    assert config.get("server", "base_url").endswith("/")

    # Setup routes.
    app = aiohttp.web.Application(loop=loop)
    app.router.add_route("GET", "/", frontend.index)
    app.router.add_route("GET", "/apidoc", frontend.apidoc)
    app.router.add_route("GET", "/legal", frontend.legal)
    app.router.add_route("GET", "/favicon.ico", static("/favicon.ico", "favicon.ico"))
    app.router.add_route("GET", "/sitemap.txt", frontend.sitemap)
    app.router.add_route("GET", "/api/v1", api.v1)
    app.router.add_route("GET", "/api/v2", api.v2)
    app.router.add_route("GET", "/api/pgn", api.pgn)
    app.router.add_static("/static/", "static")

    # Create server.
    bind = config.get("server", "bind")
    port = config.getint("server", "port")
    server = await loop.create_server(app.make_handler(), bind, port)
    print("Listening on http://%s:%d/ ..." % (bind, port))

    print("---")
    return server


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    loop = asyncio.get_event_loop()

    config = configparser.ConfigParser()

    config.read([
        os.path.join(os.path.dirname(__file__), "config.default.ini"),
        os.path.join(os.path.dirname(__file__), "config.ini"),
    ])

    loop.run_until_complete(init(config, loop))
    loop.run_forever()
