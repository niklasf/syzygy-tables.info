#!/usr/bin/env python
# -*- coding: utf-8 -*-

# This file is part of the syzygy-tables.info tablebase probing website.
# Copyright (C) 2015-2018 Niklas Fiekas <niklas.fiekas@backscattering.de>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import aiohttp.web

import jinja2

import chess
import chess.pgn
import chess.syzygy

import asyncio
import configparser
import os
import json
import logging
import warnings
import datetime
import functools

try:
    import htmlmin

    html_minify = functools.partial(htmlmin.minify, remove_optional_attribute_quotes=False)
except ImportError:
    warnings.warn("Not using HTML minification, htmlmin not imported.")

    def html_minify(html):
        return html


DEFAULT_FEN = "4k3/8/8/8/8/8/8/4K3 w - - 0 1"

EMPTY_FEN = "8/8/8/8/8/8/8/8 w - - 0 1"


def static(path):
    def handler(request):
        return aiohttp.web.FileResponse(os.path.join(os.path.dirname(__file__), path))
    return handler


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


def asset_url(path):
    return "/static/{}?mtime={}".format(path, os.path.getmtime(os.path.join(os.path.dirname(__file__), "static", path)))


def backend_session(request):
    return aiohttp.ClientSession(headers={"X-Forwarded-For": request.transport.get_extra_info("peername")[0]})


def prepare_stats(request, material):
    # Get stats and side.
    stats = request.app["stats"].get(material)
    side = "w"
    other = "b"
    if stats is None:
        stats = request.app["stats"].get(chess.syzygy.normalize_tablename(material))
        side = "b"
        other = "w"
    if stats is None:
        return None

    outcomes = {
        "white": stats[side]["wdl"]["2"] + stats[other]["wdl"]["-2"],
        "cursed": stats[side]["wdl"]["1"] + stats[other]["wdl"]["-1"],
        "draws": stats[side]["wdl"]["0"] + stats[other]["wdl"]["0"],
        "blessed": stats[side]["wdl"]["-1"] + stats[other]["wdl"]["1"],
        "black": stats[side]["wdl"]["-2"] + stats[other]["wdl"]["2"],
    }

    total = sum(outcomes.values())
    if not total:
        return None

    render = {}

    for key in outcomes:
        render[key] = outcomes[key]
        render[key + "_pct"] = round(outcomes[key] * 100 / total, 1)

    return render


routes = aiohttp.web.RouteTableDef()

@routes.get("/syzygy-vs-syzygy/{material}.pgn")
async def syzygy_vs_syzygy_pgn(request):
    # Parse FEN.
    try:
        board = chess.Board(request.query["fen"].replace("_", " "))
        board.halfmove_clock = 0
        board.fullmoves = 1
    except KeyError:
        raise aiohttp.web.HTTPBadRequest(reason="fen required")
    except ValueError:
        raise aiohttp.web.HTTPBadRequest(reason="invalid fen")

    if not board.is_valid():
        raise aiohttp.web.HTTPBadRequest(reason="illegal fen")

    # Send HTTP headers early, to let the client know we got the request.
    # Creating the actual response might take a while.
    response = aiohttp.web.StreamResponse()
    response.content_type = "application/x-chess-pgn"
    if request.version >= (1, 1):
        response.enable_chunked_encoding()
    await response.prepare(request)

    # Force reverse proxies like nginx to send the first chunk.
    await response.write("[Event \"\"]\n".encode("utf-8"))
    await response.drain()

    # Prepare PGN headers.
    game = chess.pgn.Game()
    game.setup(board)
    del game.headers["Event"]
    game.headers["Site"] = request.app["config"].get("server", "base_url") + "?fen=" + board.fen().replace(" ", "_")
    game.headers["Date"] = datetime.datetime.now().strftime("%Y.%m.%d")
    game.headers["Round"] = "-"
    game.headers["White"] = "Syzygy"
    game.headers["Black"] = "Syzygy"
    game.headers["Annotator"] = request.app["config"].get("server", "name")

    # Query backend.
    async with backend_session(request) as session:
        async with session.get(request.app["config"].get("server", "backend") + "/mainline", params={"fen": board.fen()}) as res:
            if res.status == 404:
                result = {
                    "dtz": None,
                    "mainline": [],
                }
            else:
                result = await res.json()

    # Starting comment.
    if result["dtz"] == 0:
        game.comment = "Tablebase draw"
    elif result["dtz"] is not None:
        game.comment = "DTZ %d" % (result["dtz"], )
    else:
        game.comment = "Position not in tablebases"

    # Follow the DTZ mainline.
    dtz = result["dtz"]
    node = game
    for move_info in result["mainline"]:
        move = board.push_uci(move_info["uci"])
        node = node.add_variation(move)
        dtz = move_info["dtz"]

        if board.halfmove_clock == 0:
            node.comment = "%s with DTZ %d" % (chess.syzygy.calc_key(board), dtz)

    # Final comment.
    if board.is_checkmate():
        node.comment = "Checkmate"
    elif board.is_stalemate():
        node.comment = "Stalemate"
    elif board.is_insufficient_material():
        node.comment = "Insufficient material"
    elif dtz is not None and dtz != 0 and result["winner"] is None:
        node.comment = "Draw claimed at DTZ %d" % (dtz, )

    # Set result.
    if dtz is not None:
        if result["winner"] is None:
            game.headers["Result"] = "1/2-1/2"
        elif result["winner"].startswith("w"):
            game.headers["Result"] = "1-0"
        elif result["winner"].startswith("b"):
            game.headers["Result"] = "0-1"

    # Send response.
    await response.write(str(game).encode("utf-8"))
    await response.write_eof()
    return response

@routes.get("/")
async def index(request):
    render = {}

    # Setup a board from the given valid FEN or fall back to the default FEN.
    try:
        board = chess.Board(request.query.get("fen", DEFAULT_FEN).replace("_", " "))
    except ValueError:
        try:
            board, _ = chess.Board.from_epd(request.query.get("fen", DEFAULT_FEN).replace("_", " "))
        except ValueError:
            board = chess.Board(DEFAULT_FEN)
    board.halfmove_clock = 0
    board.fullmoves = 0

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
    render["horizontal_fen"] = mirror_horizontal(fen)
    render["vertical_fen"] = mirror_vertical(fen)
    render["swapped_fen"] = swap_colors(fen)
    render["clear_fen"] = clear_fen(fen)
    render["fen_input"] = "" if board.fen() == DEFAULT_FEN else board.fen()

    # Material key for the page title.
    render["material"] = material = chess.syzygy.calc_key(board)
    render["piece_count"] = chess.popcount(board.occupied)

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
        # Query backend.
        async with backend_session(request) as session:
            async with session.get(request.app["config"].get("server", "backend"), params={"fen": board.fen()}) as res:
                if res.status != 200:
                    return aiohttp.web.Response(
                        status=res.status,
                        content_type=res.content_type,
                        body=await res.read(),
                        charset=res.charset)

                probe = await res.json()

        render["blessed_loss"] = probe["wdl"] == -1
        render["cursed_win"] = probe["wdl"] == 1

        # Set status line.
        if board.is_insufficient_material():
            render["status"] = "Draw by insufficient material"
            render["insufficient_material"] = True
        elif probe["wdl"] is None or probe["dtz"] is None:
            render["status"] = "Position not found in tablebases"
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

        render["frustrated"] = probe["wdl"] is not None and abs(probe["wdl"]) == 1

        # Label and group all legal moves.
        for move_info in probe["moves"]:
            board.push_uci(move_info["uci"])
            move_info["fen"] = board.fen()
            board.pop()

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

    # Stats.
    render["stats"] = prepare_stats(request, material)

    if "xhr" in request.query:
        template = request.app["jinja"].get_template("xhr-probe.html")
    else:
        template = request.app["jinja"].get_template("index.html")

    return aiohttp.web.Response(text=html_minify(template.render(render)), content_type="text/html")

@routes.get("/legal")
def legal(request):
    template = request.app["jinja"].get_template("legal.html")
    return aiohttp.web.Response(text=html_minify(template.render()), content_type="text/html")

@routes.get("/sitemap.txt")
def sitemap(request):
    entries = [
        "stats",
        "legal",
        "/?fen=QN4n1/6r1/3k4/8/b2K4/8/8/8_b_-_-_0_1",
    ]

    base_url = request.app["config"].get("server", "base_url")

    content = "\n".join(base_url + entry for entry in entries)
    return aiohttp.web.Response(text=content)

@routes.get("/stats")
def stats_doc(request):
    template = request.app["jinja"].get_template("stats.html")
    return aiohttp.web.Response(text=html_minify(template.render()), content_type="text/html")

@routes.get("/stats/{material}.json")
def stats_json(request):
    table = request.match_info["material"]
    if len(table) > 7 + 1 or not chess.syzygy.TABLENAME_REGEX.match(table):
        raise aiohttp.web.HTTPNotFound()

    normalized = chess.syzygy.normalize_tablename(table)
    if table != normalized:
        raise aiohttp.web.HTTPMovedPermanently(location="/stats/{}.json".format(normalized))

    try:
        stats = request.app["stats"][table]
    except KeyError:
        raise aiohttp.web.HTTPNotFound()
    else:
        return aiohttp.web.json_response(stats)


def make_app(config):
    app = aiohttp.web.Application()
    app["config"] = config

    # Check configured base url.
    assert config.get("server", "base_url").startswith("http")
    assert config.get("server", "base_url").endswith("/")

    # Configure templating.
    app["jinja"] = jinja2.Environment(loader=jinja2.FileSystemLoader("templates"))
    app["jinja"].globals["DEFAULT_FEN"] = DEFAULT_FEN
    app["jinja"].globals["STARTING_FEN"] = chess.STARTING_FEN
    app["jinja"].globals["development"] = config.getboolean("server", "development")
    app["jinja"].globals["asset_url"] = asset_url

    # Load stats.
    with open("stats.json") as f:
        app["stats"] = json.load(f)

    # Setup routes.
    app.router.add_routes(routes)
    app.router.add_static("/static", "static")
    app.router.add_route("GET", "/stats.json", static("stats.json"))
    return app


def main():
    logging.basicConfig(level=logging.DEBUG)

    config = configparser.ConfigParser()
    config.read([
        os.path.join(os.path.dirname(__file__), "config.default.ini"),
        os.path.join(os.path.dirname(__file__), "config.ini"),
    ])

    bind = config.get("server", "bind")
    port = config.getint("server", "port")

    app = make_app(config)

    print("* Server name: ", config.get("server", "name"))
    print("* Base url: ", config.get("server", "base_url"))
    aiohttp.web.run_app(app, host=bind, port=port, access_log=None)


if __name__ == "__main__":
    main()
