# This file is part of the syzygy-tables.info tablebase probing website.
# Copyright (C) 2015-2020 Niklas Fiekas <niklas.fiekas@backscattering.de>
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
import itertools
import math
import sys
import textwrap

import syzygy_tables_info.views

from typing import Any, Awaitable, Dict, List, Callable, Iterable, Optional


DEFAULT_FEN = "4k3/8/8/8/8/8/8/4K3 w - - 0 1"

EMPTY_FEN = "8/8/8/8/8/8/8/8 w - - 0 1"


def kib(num: float) -> str:
    for unit in ["KiB", "MiB", "GiB", "TiB", "PiB", "EiB", "ZiB"]:
        if abs(num) < 1024:
            return "%3.1f %s" % (num, unit)
        num /= 1024
    return "%.1f %s" % (num, "Yi")


def static(path: str, content_type: Optional[str] = None) -> Any:
    def handler(request: aiohttp.web.Request) -> aiohttp.web.FileResponse:
        headers = { "Content-Type": content_type } if content_type else None
        return aiohttp.web.FileResponse(os.path.join(os.path.dirname(__file__), "..", path), headers=headers)
    return handler


def with_turn(board: chess.Board, turn: chess.Color) -> chess.Board:
    board = board.copy(stack=False)
    board.turn = turn
    return board


@aiohttp.web.middleware
async def trust_x_forwarded_for(
    request: aiohttp.web.Request,
    handler: Callable[[aiohttp.web.Request], Awaitable[aiohttp.web.StreamResponse]]
) -> aiohttp.web.StreamResponse:
    if request.remote == "127.0.0.1":
        request = request.clone(remote=request.headers.get("X-Forwarded-For", "127.0.0.1"))
    return await handler(request)

def backend_session(request: aiohttp.web.Request) -> aiohttp.ClientSession:
    return aiohttp.ClientSession(headers={"X-Forwarded-For": request.remote})


def prepare_stats(request: aiohttp.web.Request, material: str, fen: str, active_dtz: Optional[int]) -> Optional[Dict[str, Any]]:
    render: Dict[str, Any] = {}

    # Get stats and side.
    stats = request.app["stats"].get(material)
    side = "white"
    other = "black"
    if stats is None:
        stats = request.app["stats"].get(chess.syzygy.normalize_tablename(material))
        side = "black"
        other = "white"
    if stats is None:
        return None

    material_side, _ = render["material_side"], render["material_other"] = material.split("v", 1)

    # Basic statistics.
    outcomes = {
        "white": stats["histogram"][side]["wdl"]["2"] + stats["histogram"][other]["wdl"]["-2"],
        "cursed": stats["histogram"][side]["wdl"]["1"] + stats["histogram"][other]["wdl"]["-1"],
        "draws": stats["histogram"][side]["wdl"]["0"] + stats["histogram"][other]["wdl"]["0"],
        "blessed": stats["histogram"][side]["wdl"]["-1"] + stats["histogram"][other]["wdl"]["1"],
        "black": stats["histogram"][side]["wdl"]["-2"] + stats["histogram"][other]["wdl"]["2"],
    }

    total = sum(outcomes.values())
    if not total:
        return None

    for key in outcomes:
        render[key] = outcomes[key]
        render[key + "_pct"] = round(outcomes[key] * 100 / total, 1)

    # Longest endgames.
    render["longest"] = [{
        "label": "{} {} with DTZ {}{}".format(
            material_side,
            "winning" if (longest["wdl"] > 0) == ((" " + side[0]) in longest["epd"]) else "losing",
            longest["ply"],
            " (frustrated)" if abs(longest["wdl"]) == 1 else ""),
        "fen": longest["epd"] + " 0 1",
    } for longest in stats["longest"]]

    # Histogram.
    side_winning = (" w" in fen) == (active_dtz is not None and active_dtz > 0)
    render["verb"] = "winning" if side_winning else "losing"

    win_hist = stats["histogram"][side]["win" if side_winning else "loss"]
    loss_hist = stats["histogram"][other]["loss" if side_winning else "win"]
    hist = [a + b for a, b in itertools.zip_longest(win_hist, loss_hist, fillvalue=0)]
    if not any(hist):
        return render

    maximum = max(math.log(num) if num else 0 for num in hist)

    render["histogram"] = []
    empty = 0
    for ply, num in enumerate(hist):
        if num == 0:
            empty += 1
            continue

        if empty > 5:
            render["histogram"].append({"empty": empty})
        else:
            for i in range(empty):
                render["histogram"].append({
                    "ply": ply - empty + i,
                    "num": 0,
                    "width": 0,
                })
        empty = 0

        rounding = request.app["config"].getboolean("server", "rounding")
        render["histogram"].append({
            "ply": ply,
            "num": num,
            "width": round((math.log(num) if num else 0) * 100 / maximum, 1),
            "active": active_dtz is not None and (abs(active_dtz) == ply or (rounding and active_dtz and abs(active_dtz) + 1 == ply)),
        })

    return render


def longest_fen(stats: Dict[str, Any], endgame: str) -> Optional[str]:
    if endgame == "KNvK":
        return "4k3/8/8/8/8/8/8/1N2K3 w - - 0 1"
    elif endgame == "KBvK":
        return "4k3/8/8/8/8/8/8/2B1K3 w - - 0 1"

    try:
        stats = stats[endgame]
    except KeyError:
        return None

    try:
        longest: Dict[str, Any] = max(stats["longest"], key=lambda e: e["ply"])
    except ValueError:
        return None
    else:
        return longest["epd"] + " 0 1"


def sort_key(endgame: str) -> Any:
    w, b = endgame.split("v", 1)
    return len(endgame), len(w), [-chess.syzygy.PCHR.index(p) for p in w], len(b), [-chess.syzygy.PCHR.index(p) for p in b]


routes = aiohttp.web.RouteTableDef()

@routes.get("/syzygy-vs-syzygy/{material}.pgn")
async def syzygy_vs_syzygy_pgn(request: aiohttp.web.Request) -> aiohttp.web.StreamResponse:
    # Parse FEN.
    try:
        board = chess.Board(request.query["fen"].replace("_", " "))
        board.halfmove_clock = 0
        board.fullmove_number = 1
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
                result: Dict[str, Any] = {
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
    node: chess.pgn.GameNode = game
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
    return response

@routes.get("/")
async def index(request: aiohttp.web.Request) -> aiohttp.web.Response:
    render = {}

    # Setup a board from the given valid FEN or fall back to the default FEN.
    try:
        board = chess.Board(request.query.get("fen", DEFAULT_FEN).replace("_", " "))
        board.halfmove_clock = 0
        board.fullmove_number = 1
    except ValueError:
        board = chess.Board(DEFAULT_FEN)

    # Get FENs with the current side to move, black and white to move.
    render["fen"] = fen = board.fen()
    render["white_fen"] = with_turn(board, chess.WHITE).fen()
    render["black_fen"] = with_turn(board, chess.BLACK).fen()
    render["board_fen"] = board.board_fen()
    render["check_square"] = chess.SQUARE_NAMES[board.king(board.turn)] if board.is_check() else None

    # Mirrored and color swapped FENs for the toolbar.
    render["turn"] = "white" if board.turn == chess.WHITE else "black"
    render["horizontal_fen"] = board.transform(chess.flip_horizontal).fen()
    render["vertical_fen"] = board.transform(chess.flip_vertical).fen()
    render["swapped_fen"] = with_turn(board, not board.turn).fen()
    render["clear_fen"] = with_turn(chess.Board(DEFAULT_FEN), board.turn).fen()
    render["fen_input"] = "" if board.fen() == DEFAULT_FEN else board.fen()

    # Material key for the page title.
    render["material"] = material = chess.syzygy.calc_key(board)
    render["normalized_material"] = chess.syzygy.normalize_tablename(material)
    render["piece_count"] = chess.popcount(board.occupied)

    # Moves are going to be grouped by WDL.
    grouped_moves = {-2: [], -1: [], 0: [], 1: [], 2: [], None: []}

    dtz = None
    active_dtz = None

    if not board.is_valid():
        render["status"] = "Invalid position"
        render["illegal"] = True
    elif board.is_stalemate():
        render["status"] = "Draw by stalemate"
    elif board.is_checkmate():
        active_dtz = 0
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

        dtz = probe["dtz"]
        active_dtz = dtz if dtz else None

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
            move = board.push_uci(move_info["uci"])
            move_info["fen"] = board.fen()
            board.pop()

            move_info["capture"] = board.is_capture(move)

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
    grouped_moves[-2].sort(key=lambda move: move["capture"], reverse=True)
    grouped_moves[-2].sort(key=lambda move: move["checkmate"], reverse=True)
    render["winning_moves"] = grouped_moves[-2]

    # Sort moves leading to cursed wins.
    grouped_moves[-1].sort(key=lambda move: move["uci"])
    grouped_moves[-1].sort(key=lambda move: (move["dtm"] is None, move["dtm"]))
    grouped_moves[-1].sort(key=lambda move: (move["dtz"] is None, move["dtz"]), reverse=True)
    grouped_moves[-1].sort(key=lambda move: move["zeroing"], reverse=True)
    grouped_moves[-1].sort(key=lambda move: move["capture"], reverse=True)
    render["cursed_moves"] = grouped_moves[-1]

    # Sort drawing moves.
    grouped_moves[0].sort(key=lambda move: move["uci"])
    grouped_moves[0].sort(key=lambda move: move["zeroing"], reverse=True)
    grouped_moves[0].sort(key=lambda move: move["capture"], reverse=True)
    grouped_moves[0].sort(key=lambda move: move["insufficient_material"], reverse=True)
    grouped_moves[0].sort(key=lambda move: move["stalemate"], reverse=True)
    render["drawing_moves"] = grouped_moves[0]

    # Sort moves leading to a blessed loss.
    grouped_moves[1].sort(key=lambda move: move["uci"])
    grouped_moves[1].sort(key=lambda move: (move["dtm"] is not None, move["dtm"]), reverse=True)
    grouped_moves[1].sort(key=lambda move: (move["dtz"] is None, move["dtz"]), reverse=True)
    grouped_moves[1].sort(key=lambda move: move["zeroing"])
    grouped_moves[1].sort(key=lambda move: move["capture"])
    render["blessed_moves"] = grouped_moves[1]

    # Sort losing moves.
    grouped_moves[2].sort(key=lambda move: move["uci"])
    grouped_moves[2].sort(key=lambda move: (move["dtm"] is not None, move["dtm"]), reverse=True)
    grouped_moves[2].sort(key=lambda move: (move["dtz"] is None, move["dtz"]), reverse=True)
    grouped_moves[2].sort(key=lambda move: move["zeroing"])
    grouped_moves[1].sort(key=lambda move: move["capture"])
    render["losing_moves"] = grouped_moves[2]

    # Sort unknown moves.
    grouped_moves[None].sort(key=lambda move: move["uci"])
    grouped_moves[None].sort(key=lambda move: move["zeroing"], reverse=True)
    grouped_moves[None].sort(key=lambda move: move["capture"], reverse=True)
    render["unknown_moves"] = grouped_moves[None]

    # Stats.
    render["stats"] = prepare_stats(request, material, render["fen"], active_dtz)

    # Dependencies.
    render["is_table"] = chess.syzygy.is_tablename(material, normalized=False) and material != "KvK"
    if render["is_table"]:
        render["deps"] = [{
            "material": dep,
            "longest_fen": longest_fen(request.app["stats"], dep),
        } for dep in chess.syzygy.dependencies(material)]

    if "xhr" in request.query:
        template = request.app["jinja"].get_template("xhr-probe.html")
    else:
        template = request.app["jinja"].get_template("index.html")

    return aiohttp.web.Response(text=template.render(render), content_type="text/html")

@routes.get("/legal")
async def legal(request: aiohttp.web.Request) -> aiohttp.web.Response:
    return aiohttp.web.Response(
            text=syzygy_tables_info.views.legal(development=request.app["jinja"].globals["development"]).render(),
            content_type="text/html")

@routes.get("/metrics")
async def metrics(request: aiohttp.web.Request) -> aiohttp.web.Response:
    template = request.app["jinja"].get_template("metrics.html")
    return aiohttp.web.Response(text=template.render(), content_type="text/html")

@routes.get("/robots.txt")
async def robots(request: aiohttp.web.Request) -> aiohttp.web.Response:
    return aiohttp.web.Response(text=textwrap.dedent("""\
        User-agent: SemrushBot
        User-agent: SemrushBot-SA
        User-agent: AhrefsBot
        User-agent: MegaIndex.ru
        Disallow: /

        User-agent: *
        Disallow: /syzygy-vs-syzygy/
        Disallow: /endgames.pgn
        """))

@routes.get("/sitemap.txt")
async def sitemap(request: aiohttp.web.Request) -> aiohttp.web.Response:
    entries = [
        "endgames",
        "stats",
        "legal",
        "/?fen=QN4n1/6r1/3k4/8/b2K4/8/8/8_b_-_-_0_1",
    ]

    base_url = request.app["config"].get("server", "base_url")

    content = "\n".join(base_url + entry for entry in entries)
    return aiohttp.web.Response(text=content)

@routes.get("/stats")
async def stats_doc(request: aiohttp.web.Request) -> aiohttp.web.Response:
    template = request.app["jinja"].get_template("stats.html")
    return aiohttp.web.Response(text=template.render(), content_type="text/html")

@routes.get("/stats/{material}.json")
async def stats_json(request: aiohttp.web.Request) -> aiohttp.web.Response:
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

@routes.get("/graph.dot")
@routes.get("/graph/{material}.dot")
async def graph_dot(request: aiohttp.web.Request) -> aiohttp.web.Response:
    root = request.match_info.get("material", "KPPPPPvK,KPPPPvKP,KPPPvKPP").split(",")
    if not all(chess.syzygy.is_tablename(r) for r in root):
        raise aiohttp.web.HTTPNotFound()

    closed = set(["KvK"])
    target = root[:]

    result = []
    result.append("digraph Syzygy {")
    while target:
        material = target.pop()
        if material in closed:
            continue

        deps = list(chess.syzygy.dependencies(material))
        target.extend(deps)
        if not deps and material in root:
            result.append("  {};".format(material))
        for dep in deps:
            result.append("  {} -> {};".format(material, dep))

        closed.add(material)
    result.append("}")

    result.append("")
    return aiohttp.web.Response(text="\n".join(result))

@routes.get("/download.txt")
@routes.get("/download/{material}.txt")
async def download_txt(request: aiohttp.web.Request) -> aiohttp.web.Response:
    root = request.match_info.get("material", "KPPPPPvK,KPPPPvKP,KPPPvKPP").split(",")
    if not all(chess.syzygy.is_tablename(r) for r in root):
        raise aiohttp.web.HTTPNotFound()

    source = request.query.get("source", "lichess")
    dtz = request.query.get("dtz", "all")

    try:
        max_pieces = int(request.query.get("max-pieces", "7"))
        min_pieces = int(request.query.get("min-pieces", "3"))
    except ValueError:
        raise aiohttp.web.HTTPBadRequest(reason="invalid piece count")

    tables = list(chess.syzygy.all_dependencies(root))
    tables.sort(key=sort_key)

    result = []
    for table in tables:
        piece_count = len(table) - 1
        if piece_count > max_pieces or piece_count < min_pieces:
            continue

        include_dtz = dtz in ["all", "only"] or (dtz == "root" and table in root)
        include_wdl = dtz != "only"
        if source in ["lichess", "lichess.org", "lichess.ovh", "tablebase.lichess.ovh"]:
            base = "https://tablebase.lichess.ovh/tables/standard"
            if len(table) <= 6:
                if include_wdl:
                    result.append("{}/3-4-5/{}.rtbw".format(base, table))
                if include_dtz:
                    result.append("{}/3-4-5/{}.rtbz".format(base, table))
            elif len(table) <= 7:
                if include_wdl:
                    result.append("{}/6-wdl/{}.rtbw".format(base, table))
                if include_dtz:
                    result.append("{}/6-dtz/{}.rtbz".format(base, table))
            else:
                suffix = "pawnful" if "P" in table else "pawnless"
                w, b = table.split("v")
                if include_wdl:
                    result.append("{}/7/{}v{}_{}/{}.rtbw".format(base, len(w), len(b), suffix, table))
                if include_dtz:
                    result.append("{}/7/{}v{}_{}/{}.rtbz".format(base, len(w), len(b), suffix, table))
        elif source in ["sesse", "sesse.net", "tablebase.sesse.net"]:
            base = "http://tablebase.sesse.net/syzygy"
            if len(table) <= 6:
                if include_wdl:
                    result.append("{}/3-4-5/{}.rtbw".format(base, table))
                if include_dtz:
                    result.append("{}/3-4-5/{}.rtbz".format(base, table))
            elif len(table) <= 7:
                if include_wdl:
                    result.append("{}/6-WDL/{}.rtbw".format(base, table))
                if include_dtz:
                    result.append("{}/6-DTZ/{}.rtbz".format(base, table))
            else:
                if include_wdl:
                    result.append("{}/7-WDL/{}.rtbw".format(base, table))
                if include_dtz:
                    result.append("{}/7-DTZ/{}.rtbz".format(base, table))
        elif source in ["ipfs", "ipfs.syzygy-tables.info"]:
            if len(table) <= 6:
                # More reliably seeded.
                base = "QmNbKYpPyXFAHFMnAxoc2i28Jf7jhShM8EEnfWUMv6u2DQ"
            else:
                # /ipns/ipfs.syzygy-tables.info
                base = "QmVgcSADsoW5w19MkL2RNKNPGtaz7UhGhU62XRm6pQmzct"
            if include_wdl:
                result.append("/ipfs/{}/{}.rtbw".format(base, table))
            if include_dtz:
                result.append("/ipfs/{}/{}.rtbz".format(base, table))
        elif source in ["stem", "material"]:
            result.append(table)
        elif source in ["file", "filename"]:
            if include_wdl:
                result.append("{}.rtbw".format(table))
            if include_dtz:
                result.append("{}.rtbz".format(table))
        else:
            raise aiohttp.web.HTTPBadRequest(reason="unknown source")

    result.append("")
    return aiohttp.web.Response(text="\n".join(result))

@routes.get("/endgames")
async def endgames(request: aiohttp.web.Request) -> aiohttp.web.Response:
    def subgroup(endgames: List[str], num_pieces: int, num_pawns: int) -> Iterable[str]:
        return filter(lambda t: len(t) - 1 == num_pieces and t.count("P") == num_pawns, endgames)

    endgames = list(chess.syzygy.tablenames(piece_count=7))
    endgames.sort(key=sort_key)

    render = {
        "groups": [{
            "num_pieces": num_pieces,
            "split_pawns": num_pieces >= 5,
            "subgroups": [{
                "num_pawns": num_pawns,
                "endgames": [{
                    "material": endgame,
                    "has_stats": endgame in request.app["stats"],
                    "longest_fen": longest_fen(request.app["stats"], endgame),
                    "maximal": endgame in ["KRvK", "KBNvK", "KNNvKP", "KRNvKNN", "KRBNvKQN"],
                } for endgame in subgroup(endgames, num_pieces, num_pawns)],
            } for num_pawns in range(0, num_pieces - 2 + 1)],
        } for num_pieces in range(3, 7 + 1)],
    }

    template = request.app["jinja"].get_template("endgames.html")
    return aiohttp.web.Response(text=template.render(render), content_type="text/html")


def make_app(config):
    app = aiohttp.web.Application(middlewares=[trust_x_forwarded_for])
    app["config"] = config

    # Check configured base url.
    assert config.get("server", "base_url").startswith("http")
    assert config.get("server", "base_url").endswith("/")

    # Configure templating.
    app["jinja"] = jinja2.Environment(
        loader=jinja2.FileSystemLoader("templates"),
        autoescape=jinja2.select_autoescape(["html"]))
    app["jinja"].globals["DEFAULT_FEN"] = DEFAULT_FEN
    app["jinja"].globals["STARTING_FEN"] = chess.STARTING_FEN
    app["jinja"].globals["development"] = config.getboolean("server", "development")
    app["jinja"].globals["asset_url"] = syzygy_tables_info.views.asset_url
    app["jinja"].globals["kib"] = kib

    # Load stats.
    with open("stats.json") as f:
        app["stats"] = json.load(f)

    # Setup routes.
    app.router.add_routes(routes)
    app.router.add_static("/static", "static")
    app.router.add_route("GET", "/checksums/bytes.tsv", static("checksums/bytes.tsv"))
    app.router.add_route("GET", "/checksums/tbcheck.txt", static("checksums/tbcheck.txt", content_type="text/plain"))
    app.router.add_route("GET", "/checksums/PackManifest", static("checksums/PackManifest", content_type="text/plain"))
    app.router.add_route("GET", "/checksums/B2SUM", static("checksums/B2SUM", content_type="text/plain"))
    app.router.add_route("GET", "/checksums/MD5SUM", static("checksums/MD5SUM", content_type="text/plain"))
    app.router.add_route("GET", "/checksums/SHA1SUM", static("checksums/SHA1SUM", content_type="text/plain"))
    app.router.add_route("GET", "/checksums/SHA256SUM", static("checksums/SHA256SUM", content_type="text/plain"))
    app.router.add_route("GET", "/checksums/SHA512SUM", static("checksums/SHA512SUM", content_type="text/plain"))
    app.router.add_route("GET", "/endgames.pgn", static("stats/regular/maxdtz.pgn", content_type="application/x-chess-pgn"))
    app.router.add_route("GET", "/stats.json", static("stats.json"))
    return app


def main(argv: List[str]) -> None:
    logging.basicConfig(level=logging.DEBUG)

    config = configparser.ConfigParser()
    config.read([
        os.path.join(os.path.dirname(__file__), "..", "config.default.ini"),
        os.path.join(os.path.dirname(__file__), "..", "config.ini"),
    ] + argv)

    bind = config.get("server", "bind")
    port = config.getint("server", "port")

    app = make_app(config)

    print("* Server name: ", config.get("server", "name"))
    print("* Base url: ", config.get("server", "base_url"))
    aiohttp.web.run_app(app, host=bind, port=port, access_log=None)
