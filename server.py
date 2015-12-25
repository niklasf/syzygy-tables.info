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
            content_type="application/json")


def swap_colors(fen):
    parts = fen.split()
    return parts[0].swapcase() + " " + parts[1] + " - - 0 1"

def mirror_vertical(fen):
    parts = fen.split()
    position_parts = "/".join(reversed(parts[0].split("/")))
    return position_parts + " " + parts[1] + " - - 0 1"

def mirror_horizontal(fen):
    parts = fen.split()
    position_parts = "/".join("".join(reversed(position_part)) for position_part in parts[0].split("/"))
    return position_parts + " " + parts[1] + " - - 0 1"

def clear_fen(fen):
    parts = fen.split()
    return DEFAULT_FEN.replace("w", parts[1])


def material(board):
    name = ""
    name += "K" * chess.pop_count(board.kings & board.occupied_co[chess.WHITE])
    name += "Q" * chess.pop_count(board.queens & board.occupied_co[chess.WHITE])
    name += "R" * chess.pop_count(board.rooks & board.occupied_co[chess.WHITE])
    name += "B" * chess.pop_count(board.bishops & board.occupied_co[chess.WHITE])
    name += "N" * chess.pop_count(board.knights & board.occupied_co[chess.WHITE])
    name += "P" * chess.pop_count(board.pawns & board.occupied_co[chess.WHITE])
    name += "v"
    name += "K" * chess.pop_count(board.kings & board.occupied_co[chess.BLACK])
    name += "Q" * chess.pop_count(board.queens & board.occupied_co[chess.BLACK])
    name += "R" * chess.pop_count(board.rooks & board.occupied_co[chess.BLACK])
    name += "B" * chess.pop_count(board.bishops & board.occupied_co[chess.BLACK])
    name += "N" * chess.pop_count(board.knights & board.occupied_co[chess.BLACK])
    name += "P" * chess.pop_count(board.pawns & board.occupied_co[chess.BLACK])
    return name


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
        # Setup a board from the given valid FEN or fall back to the default FEN.
        try:
            board = chess.Board(request.GET.get("fen", DEFAULT_FEN))
        except ValueError:
            try:
                board, _ = chess.Board.from_epd(request.GET.get("fen", DEFAULT_FEN))
            except ValueError:
                board = chess.Board(DEFAULT_FEN)

        # Get FENs with the current side to move, black and white to move.
        original_turn = board.turn
        board.turn = chess.WHITE
        white_fen = board.fen()
        board.turn = chess.BLACK
        black_fen = board.fen()
        board.turn = original_turn
        fen = board.fen()

        wdl = None
        winning_side = None
        winning_moves = []
        drawing_moves = []
        losing_moves = []

        if not board.is_valid():
            status = "Invalid position"
        elif board.is_stalemate():
            status = "Draw by stalemate"
            wdl = 0
        elif board.is_checkmate():
            wdl = 2
            if board.turn == chess.WHITE:
                status = "Black won by checkmate"
                winning_side = "black"
            else:
                status = "White won by checkmate"
                winning_side = "white"
        else:
            wdl = self.api.syzygy.probe_wdl(board)
            dtz = self.api.syzygy.probe_dtz(board)
            if board.is_insufficient_material():
                status = "Draw by insufficient material"
                wdl = 0
            elif dtz is None:
                status = "Position not found in tablebases"
            elif dtz == 0:
                status = "Tablebase draw"
            elif dtz > 0 and board.turn == chess.WHITE:
                status = "White is winning with DTZ %d" % (abs(dtz), )
                winning_side = "white"
                losing_side = "black"
            elif dtz < 0 and board.turn == chess.WHITE:
                status = "White is losing with DTZ %d" % (abs(dtz), )
                winning_side = "black"
                losing_side = "white"
            elif dtz > 0 and board.turn == chess.BLACK:
                status = "Black is winning with DTZ %d" % (abs(dtz), )
                winning_side = "black"
                losing_side = "white"
            elif dtz < 0 and board.turn == chess.BLACK:
                status = "Black is losing with DTZ %d" % (abs(dtz), )
                winning_side = "white"
                losing_side = "black"

            for move in board.legal_moves:
                san = board.san(move)
                uci = board.uci(move)
                board.push(move)

                move_info = {
                    "uci": uci,
                    "san": san,
                    "fen": board.epd() + " 0 1",
                    "dtz": self.api.syzygy.probe_dtz(board),
                    "dtm": self.api.gaviota.probe_dtm(board),
                    "zeroing": board.halfmove_clock == 0,
                    "checkmate": board.is_checkmate(),
                    "stalemate": board.is_stalemate(),
                    "insufficient_material": board.is_insufficient_material(),
                }

                move_info["dtm"] = abs(move_info["dtm"]) if move_info["dtm"] is not None else None

                move_info["winning"] = move_info["checkmate"] or (move_info["dtz"] is not None and move_info["dtz"] < 0)
                move_info["drawing"] = move_info["stalemate"] or move_info["insufficient_material"] or (move_info["dtz"] == 0 or (move_info["dtz"] is None and wdl is not None and wdl < 0))

                if move_info["winning"]:
                    if move_info["checkmate"]:
                        move_info["badge"] = "Checkmate"
                    elif move_info["zeroing"]:
                        move_info["badge"] = "Zeroing"
                    else:
                        move_info["badge"] = "Win with DTZ %d" % (abs(move_info["dtz"]), )

                    winning_moves.append(move_info)
                elif move_info["drawing"]:
                    if move_info["stalemate"]:
                        move_info["badge"] = "Stalemate"
                    elif move_info["insufficient_material"]:
                        move_info["badge"] = "Insufficient material"
                    elif move_info["dtz"] == 0:
                        move_info["badge"] = "Draw"
                    else:
                        move_info["badge"] = "Unknown"

                    drawing_moves.append(move_info)
                else:
                    if move_info["dtz"] is None:
                        move_info["badge"] = "Unknown"
                    elif move_info["zeroing"]:
                        move_info["badge"] = "Zeroing"
                    else:
                        move_info["badge"] = "Loss with DTZ %d" % (abs(move_info["dtz"]), )
                    losing_moves.append(move_info)

                board.pop()

        winning_moves.sort(key=lambda move: move["uci"])
        winning_moves.sort(key=lambda move: (move["dtm"] is None, move["dtm"]))
        winning_moves.sort(key=lambda move: (move["dtz"] is None, move["dtz"]), reverse=True)
        winning_moves.sort(key=lambda move: move["zeroing"], reverse=True)
        winning_moves.sort(key=lambda move: move["checkmate"], reverse=True)

        drawing_moves.sort(key=lambda move: move["uci"])
        drawing_moves.sort(key=lambda move: move["insufficient_material"], reverse=True)
        drawing_moves.sort(key=lambda move: move["stalemate"], reverse=True)

        losing_moves.sort(key=lambda move: move["uci"])
        losing_moves.sort(key=lambda move: (move["dtm"] is not None, move["dtm"]), reverse=True)
        losing_moves.sort(key=lambda move: (move["dtz"] is None, move["dtz"]), reverse=True)
        losing_moves.sort(key=lambda move: move["zeroing"])

        if "xhr" in request.GET:
            template = self.jinja.get_template("probe.html")
        else:
            template = self.jinja.get_template("index.html")

        return aiohttp.web.Response(
            text=html_minify(template.render(
                fen_input=board.epd() + " 0 1" if board.epd() + " 0 1" != DEFAULT_FEN else "",
                fen=fen,
                status=status,
                insufficient_material=board.is_insufficient_material(),
                winning_side=winning_side,
                winning_moves=winning_moves,
                drawing_moves=drawing_moves,
                losing_moves=losing_moves,
                blessed_loss=wdl == -1,
                cursed_win=wdl == 1,
                illegal=not board.is_valid(),
                not_yet_solved=board.epd() + " 0 1" == chess.STARTING_FEN,
                unknown=wdl is None,
                turn="white" if board.turn == chess.WHITE else "black",
                white_fen=white_fen,
                black_fen=black_fen,
                horizontal_fen=mirror_horizontal(fen),
                vertical_fen=mirror_vertical(fen),
                swapped_fen=swap_colors(fen),
                clear_fen=clear_fen(fen),
                DEFAULT_FEN=DEFAULT_FEN,
                material=material(board)
            )),
            content_type="text/html")

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
