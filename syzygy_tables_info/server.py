import asyncio
import configparser
import random
import datetime
import itertools
import logging
import math
import os
import textwrap
from typing import Any, Awaitable, Callable, Dict, List, Optional

import aiohttp.web
import cbor2
import chess
import chess.pgn
import chess.syzygy

import syzygy_tables_info.views
import syzygy_tables_info.tarpit
from syzygy_tables_info.model import (
    ApiResponse,
    ColorName,
    Render,
    RenderMove,
    RenderStats,
)

DEFAULT_FEN = "4k3/8/8/8/8/8/8/4K3 w - - 0 1"

EMPTY_FEN = "8/8/8/8/8/8/8/8 w - - 0 1"


kib = syzygy_tables_info.views.kib


def static(path: str, content_type: Optional[str] = None) -> Any:
    def handler(request: aiohttp.web.Request) -> aiohttp.web.FileResponse:
        headers = {"Content-Type": content_type} if content_type else None
        return aiohttp.web.FileResponse(
            os.path.join(os.path.dirname(__file__), "..", path), headers=headers
        )

    return handler


def with_turn(board: chess.Board, turn: chess.Color) -> chess.Board:
    board = board.copy(stack=False)
    board.turn = turn
    return board


def is_valid(board: chess.Board) -> bool:
    return (
        board.status()
        & ~chess.STATUS_IMPOSSIBLE_CHECK
        & ~chess.STATUS_TOO_MANY_CHECKERS
        == chess.STATUS_VALID
    )


@aiohttp.web.middleware
async def trust_x_forwarded_for(
    request: aiohttp.web.Request,
    handler: Callable[[aiohttp.web.Request], Awaitable[aiohttp.web.StreamResponse]],
) -> aiohttp.web.StreamResponse:
    if request.remote == "127.0.0.1":
        request = request.clone(
            remote=request.headers.get("X-Forwarded-For", "127.0.0.1")
        )
    return await handler(request)


def prepare_stats(
    request: aiohttp.web.Request,
    material: str,
    fen: str,
    active_dtz: Optional[int],
    precise_dtz: Optional[int],
) -> Optional[RenderStats]:
    render: RenderStats = {}

    # Get stats and side.
    stats = syzygy_tables_info.stats.STATS.get(material)
    side: ColorName = "white"
    other: ColorName = "black"
    if stats is None:
        stats = syzygy_tables_info.stats.STATS.get(
            chess.syzygy.normalize_tablename(material)
        )
        side = "black"
        other = "white"
    if stats is None:
        return None

    material_side, _ = render["material_side"], render["material_other"] = (
        material.split("v", 1)
    )

    # Basic statistics.
    render["white"] = (
        stats["histogram"][side]["wdl"]["2"] + stats["histogram"][other]["wdl"]["-2"]
    )
    render["cursed"] = (
        stats["histogram"][side]["wdl"]["1"] + stats["histogram"][other]["wdl"]["-1"]
    )
    render["draws"] = (
        stats["histogram"][side]["wdl"]["0"] + stats["histogram"][other]["wdl"]["0"]
    )
    render["blessed"] = (
        stats["histogram"][side]["wdl"]["-1"] + stats["histogram"][other]["wdl"]["1"]
    )
    render["black"] = (
        stats["histogram"][side]["wdl"]["-2"] + stats["histogram"][other]["wdl"]["2"]
    )

    total = (
        render["white"]
        + render["cursed"]
        + render["draws"]
        + render["blessed"]
        + render["black"]
    )
    if not total:
        return None

    render["white_pct"] = round(render["white"] * 100 / total, 1)
    render["cursed_pct"] = round(render["cursed"] * 100 / total, 1)
    render["draws_pct"] = round(render["draws"] * 100 / total, 1)
    render["blessed_pct"] = round(render["blessed"] * 100 / total, 1)
    render["black_pct"] = round(render["black"] * 100 / total, 1)

    # Longest endgames.
    render["longest"] = [
        {
            "label": "{} {} with DTZ {}{}".format(
                material_side,
                "winning"
                if (longest["wdl"] > 0) == ((" " + side[0]) in longest["epd"])
                else "losing",
                longest["ply"],
                " (frustrated)" if abs(longest["wdl"]) == 1 else "",
            ),
            "fen": longest["epd"] + " 0 1",
        }
        for longest in stats["longest"]
    ]

    # Histogram.
    side_winning = (" w" in fen) == (active_dtz is not None and active_dtz > 0)
    render["verb"] = "winning" if side_winning else "losing"

    win_hist = (
        stats["histogram"][side]["win"]
        if side_winning
        else stats["histogram"][side]["loss"]
    )
    loss_hist = (
        stats["histogram"][other]["loss"]
        if side_winning
        else stats["histogram"][other]["win"]
    )
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
                render["histogram"].append(
                    {
                        "ply": ply - empty + i,
                        "num": 0,
                        "width": 0,
                        "active": False,
                        "empty": 0,
                    }
                )
        empty = 0

        rounding = active_dtz != precise_dtz
        render["histogram"].append(
            {
                "ply": ply,
                "num": num,
                "width": int(round((math.log(num) if num else 0) * 100 / maximum, 1)),
                "active": active_dtz is not None
                and (
                    abs(active_dtz) == ply
                    or bool(rounding and active_dtz and abs(active_dtz) + 1 == ply)
                ),
                "empty": 0,
            }
        )

    return render


def sort_key(endgame: str) -> Any:
    w, b = endgame.split("v", 1)
    return (
        len(endgame),
        len(w),
        [-chess.syzygy.PCHR.index(p) for p in w],
        len(b),
        [-chess.syzygy.PCHR.index(p) for p in b],
    )


routes = aiohttp.web.RouteTableDef()


@routes.get("/syzygy-vs-syzygy/{material}.pgn")
async def syzygy_vs_syzygy_pgn(
    request: aiohttp.web.Request,
) -> aiohttp.web.StreamResponse:
    # Parse FEN.
    try:
        board = chess.Board(request.query["fen"].replace("_", " "))
        board.halfmove_clock = 0
        board.fullmove_number = 1
    except KeyError:
        raise aiohttp.web.HTTPBadRequest(reason="fen required")
    except ValueError:
        raise aiohttp.web.HTTPBadRequest(reason="invalid fen")

    if not is_valid(board):
        raise aiohttp.web.HTTPBadRequest(reason="illegal fen")

    # Send HTTP headers early, to let the client know we got the request.
    # Creating the actual response might take a while.
    response = aiohttp.web.StreamResponse()
    response.content_type = "application/x-chess-pgn"
    if request.version >= (1, 1):
        response.enable_chunked_encoding()
    await response.prepare(request)

    # Force reverse proxies like nginx to send the first chunk.
    await response.write('[Event ""]\n'.encode("utf-8"))

    # Prepare PGN headers.
    game = chess.pgn.Game()
    game.setup(board)
    del game.headers["Event"]
    game.headers["Site"] = (
        request.app["config"].get("server", "base_url")
        + "?fen="
        + board.fen().replace(" ", "_")
    )
    game.headers["Date"] = datetime.datetime.now().strftime("%Y.%m.%d")
    game.headers["Round"] = "-"
    game.headers["White"] = "Syzygy"
    game.headers["Black"] = "Syzygy"
    game.headers["Annotator"] = request.app["config"].get("server", "name")

    # Query backend.
    async with request.app["session"].get(
        request.app["config"].get("server", "backend") + "/mainline",
        headers={
            "Accept": "application/cbor",
            "X-Forwarded-For": request.remote,
            "User-Agent": f"{request.headers.get('User-Agent', '-')} via syzygy-tables.info",
        },
        params={"fen": board.fen()},
    ) as res:
        if res.status != 200:
            result: Dict[str, Any] = {
                "dtz": None,
                "mainline": [],
            }
        else:
            result = cbor2.loads(await res.read())

    # Starting comment.
    if result["dtz"] == 0:
        game.comment = "Tablebase draw"
    elif result["dtz"] is not None:
        game.comment = "DTZ %d" % (result["dtz"],)
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
    if res.status not in [200, 404]:
        node.comment = f"Unexpected internal status code {res.status}"
    elif board.is_checkmate():
        node.comment = "Checkmate"
    elif board.is_stalemate():
        node.comment = "Stalemate"
    elif board.is_insufficient_material():
        node.comment = "Insufficient material"
    elif dtz is not None and dtz != 0 and result["winner"] is None:
        node.comment = "Draw claimed at DTZ %d" % (dtz,)

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
    render: Render = {}

    # Setup a board from the given valid FEN or fall back to the default FEN.
    try:
        board = chess.Board(request.query.get("fen", DEFAULT_FEN).replace("_", " "))
        board.halfmove_clock = 0
        board.fullmove_number = 1
    except ValueError:
        board = chess.Board(DEFAULT_FEN)

    # Get FENs with the current side to move, black and white to move.
    render["fen"] = board.fen()
    render["white_fen"] = with_turn(board, chess.WHITE).fen()
    render["black_fen"] = with_turn(board, chess.BLACK).fen()

    # Thumbail.
    render["thumbnail_url"] = (
        f"https://backscattering.de/web-boardimage/board.png?fen={board.board_fen()}"
    )
    king = board.king(board.turn)
    if king is not None and board.is_check():
        render["thumbnail_url"] += "&check=" + chess.SQUARE_NAMES[king]

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

    # Moves are going to be grouped by WDL.
    grouped_moves: Dict[Optional[int], List[RenderMove]] = {
        -2: [],
        -1: [],
        0: [],
        1: [],
        2: [],
        None: [],
    }

    # Defaults.
    render["winning_side"] = None
    render["illegal"] = False
    render["insufficient_material"] = False
    render["frustrated"] = False
    render["blessed_loss"] = False
    render["cursed_win"] = False
    render["dtz"] = None
    render["dtm"] = None
    render["tarpit"] = None

    dtz = None
    active_dtz = None
    precise_dtz = None

    if not is_valid(board):
        render["status"] = "Invalid position"
        render["illegal"] = True
    elif board.is_stalemate():
        render["status"] = "Draw by stalemate"
    elif board.is_checkmate():
        active_dtz = 0
        precise_dtz = 0
        if board.turn == chess.WHITE:
            render["status"] = "Black won by checkmate"
            render["winning_side"] = "black"
        else:
            render["status"] = "White won by checkmate"
            render["winning_side"] = "white"
    else:
        # Query backend.
        async with request.app["session"].get(
            request.app["config"].get("server", "backend"),
            headers={
                "Accept": "application/cbor",
                "X-Forwarded-For": request.remote,
                "User-Agent": f"{request.headers.get('User-Agent', '-')} via syzygy-tables.info",
            },
            params={"fen": board.fen()},
        ) as res:
            if res.status != 200:
                return aiohttp.web.Response(
                    status=res.status,
                    content_type=res.content_type,
                    body=await res.read(),
                    charset=res.charset,
                )

            probe: ApiResponse = cbor2.loads(await res.read())

        dtz = probe.get("dtz")
        active_dtz = dtz or None
        precise_dtz = probe.get("precise_dtz") or None

        render["blessed_loss"] = probe["category"] == "blessed-loss"
        render["cursed_win"] = probe["category"] == "cursed-win"
        render["dtz"] = dtz
        render["dtm"] = probe.get("dtm")

        # Set status line.
        if board.is_insufficient_material():
            render["status"] = "Draw by insufficient material"
            render["insufficient_material"] = True
        elif dtz is None:
            render["status"] = "Position not found in tablebases"
        elif dtz == 0:
            render["status"] = "Tablebase draw"
        elif dtz > 0 and board.turn == chess.WHITE:
            render["status"] = "White is winning"
            render["winning_side"] = "white"
        elif dtz < 0 and board.turn == chess.WHITE:
            render["status"] = "White is losing"
            render["winning_side"] = "black"
        elif dtz > 0 and board.turn == chess.BLACK:
            render["status"] = "Black is winning"
            render["winning_side"] = "black"
        elif dtz < 0 and board.turn == chess.BLACK:
            render["status"] = "Black is losing"
            render["winning_side"] = "white"

        render["frustrated"] = probe["category"] in ["blessed-loss", "cursed-win"]

        # Label and group all legal moves.
        for move_info in probe["moves"]:
            if move_info.get("checkmate"):
                badge = "Checkmate"
            elif move_info.get("stalemate"):
                badge = "Stalemate"
            elif move_info.get("insufficient_material"):
                badge = "Insufficient material"
            elif move_info.get("dtz") is None:
                badge = "Unknown"
            elif move_info["dtz"] == 0:
                badge = "Draw"
            elif move_info.get("zeroing"):
                badge = "Zeroing"
            elif move_info["dtz"] < 0:
                badge = "Win with DTZ %d" % (abs(move_info["dtz"]),)
            else:
                badge = "Loss with DTZ %d" % (move_info["dtz"],)

            if move_info["category"] in ["loss", "maybe-loss"]:
                wdl: Optional[int] = -2
            elif move_info["category"] == "blessed-loss":
                wdl = -1
            elif move_info["category"] == "draw":
                wdl = 0
            elif move_info["category"] == "cursed-win":
                wdl = 1
            elif move_info["category"] in ["win", "maybe-win"]:
                wdl = 2
            else:
                wdl = None

            dtm = abs(move_info["dtm"]) if move_info.get("dtm") is not None else None

            try:
                board.push_uci(move_info["uci"])
                grouped_moves[wdl].append(
                    {
                        "uci": move_info["uci"],
                        "san": move_info["san"],
                        "fen": board.fen(),
                        "wdl": wdl,
                        "dtz": move_info.get("dtz"),
                        "dtm": dtm,
                        "zeroing": move_info["zeroing"],
                        "capture": "x" in move_info["san"],
                        "checkmate": move_info["checkmate"],
                        "stalemate": move_info["stalemate"],
                        "insufficient_material": move_info["insufficient_material"],
                        "badge": badge,
                    }
                )
            finally:
                board.pop()

    # Sort winning moves.
    grouped_moves[-2].sort(key=lambda move: move["uci"])
    grouped_moves[-2].sort(key=lambda move: (move["dtm"] is None, move["dtm"]))
    grouped_moves[-2].sort(
        key=lambda move: (move["dtz"] is None, move["dtz"]), reverse=True
    )
    grouped_moves[-2].sort(key=lambda move: move["zeroing"], reverse=True)
    grouped_moves[-2].sort(key=lambda move: move["capture"], reverse=True)
    grouped_moves[-2].sort(key=lambda move: move["checkmate"], reverse=True)
    render["winning_moves"] = grouped_moves[-2]

    # Sort unknown moves.
    grouped_moves[None].sort(key=lambda move: move["uci"])
    grouped_moves[None].sort(key=lambda move: move["zeroing"], reverse=True)
    grouped_moves[None].sort(key=lambda move: move["capture"], reverse=True)
    render["unknown_moves"] = grouped_moves[None]

    # Sort moves leading to cursed wins.
    grouped_moves[-1].sort(key=lambda move: move["uci"])
    grouped_moves[-1].sort(key=lambda move: (move["dtm"] is None, move["dtm"]))
    grouped_moves[-1].sort(
        key=lambda move: (move["dtz"] is None, move["dtz"]), reverse=True
    )
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
    grouped_moves[1].sort(
        key=lambda move: (move["dtm"] is not None, move["dtm"]), reverse=True
    )
    grouped_moves[1].sort(
        key=lambda move: (move["dtz"] is None, move["dtz"]), reverse=True
    )
    grouped_moves[1].sort(key=lambda move: move["zeroing"])
    grouped_moves[1].sort(key=lambda move: move["capture"])
    render["blessed_moves"] = grouped_moves[1]

    # Sort losing moves.
    grouped_moves[2].sort(key=lambda move: move["uci"])
    grouped_moves[2].sort(
        key=lambda move: (move["dtm"] is not None, move["dtm"]), reverse=True
    )
    grouped_moves[2].sort(
        key=lambda move: (move["dtz"] is None, move["dtz"]), reverse=True
    )
    grouped_moves[2].sort(key=lambda move: move["zeroing"])
    grouped_moves[1].sort(key=lambda move: move["capture"])
    render["losing_moves"] = grouped_moves[2]

    # Stats.
    render["stats"] = prepare_stats(
        request, material, render["fen"], active_dtz, precise_dtz
    )

    # Dependencies.
    render["is_table"] = (
        chess.syzygy.is_tablename(material, normalized=False) and material != "KvK"
    )
    if render["is_table"]:
        render["deps"] = [
            {
                "material": dep,
                "longest_fen": syzygy_tables_info.stats.longest_fen(dep),
            }
            for dep in chess.syzygy.dependencies(material)
        ]

    if "xhr" in request.query:
        html = syzygy_tables_info.views.xhr_probe(render=render).render()
    else:
        if request.app["tarpit"] and "fen" in request.query:
            await asyncio.sleep(min(random.lognormvariate(1.1, 0.4), 9))
            rng = random.Random(request.query["fen"])
            num_words = 12
            if 4 <= chess.popcount(board.occupied) <= 8:
                num_words += rng.randint(0, 1 + 50 * sum(len(g) for g in grouped_moves.values()))
            render["tarpit"] = syzygy_tables_info.tarpit.MARKOV_CHAIN.generate_text(num_words, rng)

        html = syzygy_tables_info.views.index(
            development=request.app["development"], render=render
        ).render()

    return aiohttp.web.Response(text=html, content_type="text/html")


@routes.get("/legal")
async def legal(request: aiohttp.web.Request) -> aiohttp.web.Response:
    return aiohttp.web.Response(
        text=syzygy_tables_info.views.legal(
            development=request.app["development"]
        ).render(),
        content_type="text/html",
    )


@routes.get("/metrics")
async def metrics(request: aiohttp.web.Request) -> aiohttp.web.Response:
    return aiohttp.web.Response(
        text=syzygy_tables_info.views.metrics(
            development=request.app["development"]
        ).render(),
        content_type="text/html",
    )


@routes.get("/robots.txt")
async def robots(request: aiohttp.web.Request) -> aiohttp.web.Response:
    return aiohttp.web.Response(
        text=textwrap.dedent("""\
        User-agent: *
        Disallow: /?fen=*
        Disallow: /syzygy-vs-syzygy/
        Disallow: /endgames.pgn
        """)
    )


@routes.get("/sitemap.txt")
async def sitemap(request: aiohttp.web.Request) -> aiohttp.web.Response:
    entries = [
        "endgames",
        "metrics",
        "stats",
        "legal",
    ]

    base_url = request.app["config"].get("server", "base_url")

    content = "\n".join(base_url + entry for entry in entries)
    return aiohttp.web.Response(text=content)


@routes.get("/stats")
async def stats_doc(request: aiohttp.web.Request) -> aiohttp.web.Response:
    return aiohttp.web.Response(
        text=syzygy_tables_info.views.stats(
            development=request.app["development"]
        ).render(),
        content_type="text/html",
    )


@routes.get("/stats/{material}.json")
async def stats_json(request: aiohttp.web.Request) -> aiohttp.web.Response:
    table = request.match_info["material"]
    if len(table) > 7 + 1 or not chess.syzygy.TABLENAME_REGEX.match(table):
        raise aiohttp.web.HTTPNotFound()

    normalized = chess.syzygy.normalize_tablename(table)
    if table != normalized:
        raise aiohttp.web.HTTPMovedPermanently(
            location="/stats/{}.json".format(normalized)
        )

    try:
        stats = syzygy_tables_info.stats.STATS[table]
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
                    result.append("{}/3-4-5-wdl/{}.rtbw".format(base, table))
                if include_dtz:
                    result.append("{}/3-4-5-dtz/{}.rtbz".format(base, table))
            elif len(table) <= 7:
                if include_wdl:
                    result.append("{}/6-wdl/{}.rtbw".format(base, table))
                if include_dtz:
                    result.append("{}/6-dtz/{}.rtbz".format(base, table))
            else:
                suffix = "pawnful" if "P" in table else "pawnless"
                w, b = table.split("v")
                if include_wdl:
                    result.append(
                        "{}/7/{}v{}_{}/{}.rtbw".format(
                            base, len(w), len(b), suffix, table
                        )
                    )
                if include_dtz:
                    result.append(
                        "{}/7/{}v{}_{}/{}.rtbz".format(
                            base, len(w), len(b), suffix, table
                        )
                    )
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
    return aiohttp.web.Response(
        text=syzygy_tables_info.views.endgames(
            development=request.app["development"]
        ).render(),
        content_type="text/html",
    )


async def make_app(config: configparser.ConfigParser) -> aiohttp.web.Application:
    app = aiohttp.web.Application(middlewares=[trust_x_forwarded_for])
    app["session"] = aiohttp.ClientSession()
    app["config"] = config
    app["development"] = config.getboolean("server", "development")
    app["tarpit"] = config.getboolean("server", "tarpit")

    # Check configured base url.
    assert config.get("server", "base_url").startswith("http")
    assert config.get("server", "base_url").endswith("/")

    # Setup routes.
    app.router.add_routes(routes)
    app.router.add_static("/static", "static")
    app.router.add_route("GET", "/checksums/bytes.tsv", static("checksums/bytes.tsv"))
    app.router.add_route(
        "GET",
        "/checksums/tbcheck.txt",
        static("checksums/tbcheck.txt", content_type="text/plain"),
    )
    app.router.add_route(
        "GET", "/checksums/b2", static("checksums/b2", content_type="text/plain")
    )
    app.router.add_route(
        "GET", "/checksums/b3", static("checksums/b3", content_type="text/plain")
    )
    app.router.add_route(
        "GET", "/checksums/md5", static("checksums/md5", content_type="text/plain")
    )
    app.router.add_route(
        "GET", "/checksums/sha1", static("checksums/sha1", content_type="text/plain")
    )
    app.router.add_route(
        "GET",
        "/checksums/sha256",
        static("checksums/sha256", content_type="text/plain"),
    )
    app.router.add_route(
        "GET",
        "/checksums/sha512",
        static("checksums/sha512", content_type="text/plain"),
    )
    app.router.add_route(
        "GET",
        "/checksums/sha3-224",
        static("checksums/sha3-224", content_type="text/plain"),
    )
    app.router.add_route(
        "GET",
        "/endgames.pgn",
        static("stats/regular/maxdtz.pgn", content_type="application/x-chess-pgn"),
    )
    app.router.add_route("GET", "/stats.json", static("stats.json"))

    # Legacy routes.
    app.router.add_route(
        "GET", "/checksums/B2SUM", static("checksums/b2", content_type="text/plain")
    )
    app.router.add_route(
        "GET", "/checksums/MD5SUM", static("checksums/md5", content_type="text/plain")
    )
    app.router.add_route(
        "GET", "/checksums/SHA1SUM", static("checksums/sha1", content_type="text/plain")
    )
    app.router.add_route(
        "GET",
        "/checksums/SHA256SUM",
        static("checksums/sha256", content_type="text/plain"),
    )
    app.router.add_route(
        "GET",
        "/checksums/SHA512SUM",
        static("checksums/sha512", content_type="text/plain"),
    )

    return app


def main(argv: List[str]) -> None:
    logging.basicConfig(level=logging.DEBUG)

    config = configparser.ConfigParser()
    config.read(
        [
            os.path.join(os.path.dirname(__file__), "..", "config.default.ini"),
            os.path.join(os.path.dirname(__file__), "..", "config.ini"),
        ]
        + argv
    )

    bind = config.get("server", "bind")
    port = config.getint("server", "port")

    print("* Server name: ", config.get("server", "name"))
    print("* Base url: ", config.get("server", "base_url"))
    aiohttp.web.run_app(make_app(config), host=bind, port=port, access_log=None)
