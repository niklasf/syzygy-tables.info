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
import datetime

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

        bm = self.dtz_bestmove(board, result)
        result["bestmove"] = bm.uci() if bm else None

        # Collapse move information to produce legacy API output.
        for move in result["moves"]:
            result["moves"][move] = result["moves"][move]["dtz"]

        return jsonp(request, result)

    async def v2(self, request):
        board = self.get_board(request)

        result = await self.probe_async(board, load_root=True, load_dtz=True, load_dtm=True, load_wdl=True)

        bm = self.dtz_bestmove(board, result)
        result["bestmove"] = bm.uci() if bm else None

        return jsonp(request, result)

    def dtz_bestmove(self, board, probe_result):
        def result(move, key, default=None):
            res = probe_result["moves"][move.uci()].get(key)
            if res is None:
                return default
            else:
                return res

        def zeroing(move):
            try:
                board.push(move)
                return board.halfmove_clock == 0
            finally:
                board.pop()

        def checkmate(move):
            try:
                board.push(move)
                return board.is_checkmate()
            finally:
                board.pop()

        def definite_draw(move):
            try:
                board.push(move)
                return board.is_insufficient_material() or board.is_stalemate()
            finally:
                board.pop()

        moves = list(board.legal_moves)
        moves.sort(key=lambda move: move.uci())
        moves.sort(key=lambda move: (result(move, "dtm") is None, result(move, "dtm")), reverse=True)
        moves.sort(key=lambda move: (result(move, "dtz") is None, result(move, "dtz")), reverse=True)
        moves.sort(key=lambda move: zeroing(move) if result(move, "wdl", 0) > 0 else not zeroing(move))
        moves.sort(key=lambda move: definite_draw(move))
        moves.sort(key=lambda move: (result(move, "wdl") is None, result(move, "wdl")))
        moves.sort(key=lambda move: checkmate(move), reverse=True)

        if moves and result(moves[0], "dtz") is not None:
            return moves[0]

    async def syzygy_vs_syzygy_pgn(self, request):
        board = self.get_board(request)

        # Send HTTP headers early, to let the client know wo got the request.
        # Creating the actual response might take a while.
        response = aiohttp.web.StreamResponse()
        response.content_type = "application/x-chess-pgn"
        if request.version >= (1, 1):
            response.enable_chunked_encoding()
        await response.prepare(request)

        # Force reverse proxies like nginx to send the first chunk.
        response.write("[Event \"\"]\n".encode("utf-8"))
        await response.drain()

        # Prepare PGN headers.
        game = chess.pgn.Game()
        game.setup(board)
        del game.headers["Event"]
        game.headers["Site"] = self.config.get("server", "base_url") + "?fen=" + board.fen().replace(" ", "%20")
        game.headers["Date"] = datetime.datetime.now().strftime("%Y.%m.%d")
        del game.headers["Round"]
        game.headers["White"] = "Syzygy"
        game.headers["Black"] = "Syzygy"
        game.headers["Annotator"] = self.config.get("server", "name")

        result = await self.probe_async(board, load_root=True)
        if result["dtz"] is not None:
            game.comment = "DTZ %d" % (result["dtz"], )
        else:
            game.comment = "Position not in tablebases"

        # Follow the DTZ mainline.
        node = game
        while not board.is_game_over(claim_draw=True):
            result = await self.probe_async(board, load_dtz=True, load_wdl=True)
            move = self.dtz_bestmove(board, result)
            if not move:
                break

            board.push(move)
            node = node.add_variation(move)

            if board.halfmove_clock == 0:
                result = await self.probe_async(board, load_root=True)
                node.comment = "%s with DTZ %d" % (material(board), result["dtz"])

        # Set PGN result.
        if board.is_checkmate():
            node.comment = "Checkmate"
        elif board.is_stalemate():
            node.comment = "Stalemate"
        elif board.is_insufficient_material():
            node.comment = "Insufficient material"
        elif board.can_claim_draw():
            result = await self.probe_async(board, load_root=True)
            node.comment = "Draw claimed at DTZ %d" % (result["dtz"], )

        game.headers["Result"] = board.result(claim_draw=True)

        # Send response.
        response.write(str(game).encode("utf-8"))
        await response.write_eof()
        return response


class Frontend(object):

    def __init__(self, config, api, loop):
        self.config = config
        self.api = api
        self.loop = loop

        self.jinja = jinja2.Environment(
            loader=jinja2.FileSystemLoader("templates"))

    async def index(self, request):
        render = {}
        render["DEFAULT_FEN"] = DEFAULT_FEN
        render["STARTING_FEN"] = chess.STARTING_FEN

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
        render["white_fen"] = board.fen()
        board.turn = chess.BLACK
        render["black_fen"] = board.fen()
        board.turn = original_turn
        render["fen"] = fen = board.fen()

        # Mirrored and color swapped FENs for the toolbar.
        render["turn"] = "white" if board.turn == chess.WHITE else "black"
        render["horizontral_fen"] = mirror_horizontal(fen)
        render["vertical_fen"] = mirror_vertical(fen)
        render["swapped_fen"] = swap_colors(fen)
        render["clear_fen"] = clear_fen(fen)
        render["fen_input"] = "" if board.epd() + " 0 1" == DEFAULT_FEN else board.epd() + " 0 1"

        # Material key for the page title.
        render["material"] = material(board)

        # Moves are going to be grouped by WDL.
        grouped_moves = {-2: [], -1: [], 0: [], 1: [], 2: [], None: []}

        if not board.is_valid():
            render["status"] = "Invalid position"
            render["illegal"] = True
        elif board.is_stalemate():
            render["status"] = "Draw by stalemate"
        elif board.is_checkmate():
            if board.turn == chess.WHITE:
                render["status"] = "Black won by checkmate"
                render["winning_side"] = "black"
            else:
                render["status"] = "White won by checkmate"
                render["winning_side"] = "white"
        else:
            # Probe.
            probe = await self.api.probe_async(board, load_root=True, load_dtz=True, load_wdl=True, load_dtm=True)
            render["blessed_loss"] = probe["wdl"] == -1
            render["cursed_win"] = probe["wdl"] == 1

            # Set status line.
            if board.is_insufficient_material():
                render["status"] = "Draw by insufficient material"
                render["insufficient_material"] = True
            elif probe["wdl"] is None or probe["dtz"] is None:
                render["status"] = "Position not found in tablebases"
                render["unknown"] = True
            elif probe["wdl"] == 0:
                render["status"] = "Tablebase draw"
            elif probe["dtz"] > 0 and board.turn == chess.WHITE:
                render["status"] = "White is winning with DTZ %d" % (abs(probe["dtz"]), )
                render["winning_side"] = "white"
            elif probe["dtz"] < 0 and board.turn == chess.WHITE:
                render["status"] = "White is losing with DTZ %d" % (abs(probe["dtz"]), )
                render["winning_side"] = "black"
            elif probe["dtz"] > 0 and board.turn == chess.BLACK:
                render["status"] = "Black is winning with DTZ %d" % (abs(probe["dtz"]), )
                render["winning_side"] = "black"
            elif probe["dtz"] < 0 and board.turn == chess.BLACK:
                render["status"] = "Black is losing with DTZ %d" % (abs(probe["dtz"]), )
                render["winning_side"] = "white"

            # Label and group all legal moves.
            for move in board.legal_moves:
                san = board.san(move)
                uci = board.uci(move)
                board.push(move)

                move_info = {
                    "uci": uci,
                    "san": san,
                    "fen": board.epd() + " 0 1",
                    "wdl": probe["moves"][uci]["wdl"],
                    "dtz": probe["moves"][uci]["dtz"],
                    "dtm": probe["moves"][uci]["dtm"],
                    "zeroing": board.halfmove_clock == 0,
                    "checkmate": board.is_checkmate(),
                    "stalemate": board.is_stalemate(),
                    "insufficient_material": board.is_insufficient_material(),
                }

                move_info["dtm"] = abs(move_info["dtm"]) if move_info["dtm"] is not None else None

                if move_info["checkmate"]:
                    move_info["wdl"] = -2
                elif move_info["stalemate"] or move_info["insufficient_material"]:
                    move_info["wdl"] = 0

                if move_info["checkmate"]:
                    move_info["badge"] = "Checkmate"
                elif move_info["stalemate"]:
                    move_info["badge"] = "Stalemate"
                elif move_info["insufficient_material"]:
                    move_info["badge"] = "Insufficient material"
                elif move_info["dtz"] == 0:
                    move_info["badge"] = "Draw"
                elif move_info["dtz"] is None:
                    move_info["badge"] = "Unknown"
                elif move_info["zeroing"]:
                    move_info["badge"] = "Zeroing"
                elif move_info["dtz"] < 0:
                    move_info["badge"] = "Win with DTZ %d" % (abs(move_info["dtz"]), )
                elif move_info["dtz"] > 0:
                    move_info["badge"] = "Loss with DTZ %d" % (abs(move_info["dtz"]), )

                grouped_moves[move_info["wdl"]].append(move_info)

                board.pop()

        # Sort winning moves.
        grouped_moves[-2].sort(key=lambda move: move["uci"])
        grouped_moves[-2].sort(key=lambda move: (move["dtm"] is None, move["dtm"]))
        grouped_moves[-2].sort(key=lambda move: (move["dtz"] is None, move["dtz"]), reverse=True)
        grouped_moves[-2].sort(key=lambda move: move["zeroing"], reverse=True)
        grouped_moves[-2].sort(key=lambda move: move["checkmate"], reverse=True)
        render["winning_moves"] = grouped_moves[-2]

        # Sort moves leading to cursed wins.
        grouped_moves[-1].sort(key=lambda move: move["uci"])
        grouped_moves[-1].sort(key=lambda move: (move["dtm"] is None, move["dtm"]))
        grouped_moves[-1].sort(key=lambda move: (move["dtz"] is None, move["dtz"]), reverse=True)
        grouped_moves[-1].sort(key=lambda move: move["zeroing"], reverse=True)
        render["cursed_moves"] = grouped_moves[-1]

        # Sort drawing moves.
        grouped_moves[0].sort(key=lambda move: move["uci"])
        grouped_moves[0].sort(key=lambda move: move["insufficient_material"], reverse=True)
        grouped_moves[0].sort(key=lambda move: move["stalemate"], reverse=True)
        render["drawing_moves"] = grouped_moves[0]

        # Sort moves leading to a blessed loss.
        grouped_moves[1].sort(key=lambda move: move["uci"])
        grouped_moves[1].sort(key=lambda move: (move["dtm"] is not None, move["dtm"]), reverse=True)
        grouped_moves[1].sort(key=lambda move: (move["dtz"] is None, move["dtz"]), reverse=True)
        grouped_moves[1].sort(key=lambda move: move["zeroing"])
        render["blessed_moves"] = grouped_moves[1]

        # Sort losing moves.
        grouped_moves[2].sort(key=lambda move: move["uci"])
        grouped_moves[2].sort(key=lambda move: (move["dtm"] is not None, move["dtm"]), reverse=True)
        grouped_moves[2].sort(key=lambda move: (move["dtz"] is None, move["dtz"]), reverse=True)
        grouped_moves[2].sort(key=lambda move: move["zeroing"])
        render["losing_moves"] = grouped_moves[2]

        # Sort unknown moves.
        grouped_moves[None].sort(key=lambda move: move["uci"])
        render["unknown_moves"] = grouped_moves[None]

        if "xhr" in request.GET:
            template = self.jinja.get_template("probe.html")
        else:
            template = self.jinja.get_template("index.html")

        return aiohttp.web.Response(
            text=html_minify(template.render(render)),
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
                result = await self.api.probe_async(board, load_root=True, load_dtz=True, load_dtm=True, load_wdl=True)

                bm = self.api.dtz_bestmove(board, result)
                result["bestmove"] = bm.uci() if bm else None

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
    app.router.add_route("GET", "/syzygy-vs-syzygy/{material}.pgn", api.syzygy_vs_syzygy_pgn)
    app.router.add_static("/static/", "static")

    # Create server.
    bind = config.get("server", "bind")
    port = config.getint("server", "port")
    server = await loop.create_server(app.make_handler(), bind, port)
    print("Listening on: http://%s:%d/ ..." % (bind, port))
    print("* Server name: %s" % (config.get("server", "name"), ))
    print("* Base url: %s" % (config.get("server", "base_url"), ))

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
