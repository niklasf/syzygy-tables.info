#!/usr/bin/python2

from flask import Flask
from flask import render_template
from flask import current_app
from flask import request
from flask import abort
from flask import jsonify
from flask import send_from_directory

import chess
import chess.syzygy

import functools
import os.path
import warnings
import json
import cPickle as pickle

try:
    from htmlmin import minify as html_minify
except ImportError:
    warnings.warn("Not using HTML minification, htmlmin not imported.")

    def html_minify(html):
        return html


DEFAULT_FEN = "4k3/8/8/8/8/8/8/4K3 w - - 0 1"


app = Flask(__name__)

tablebases = chess.syzygy.Tablebases()
num = 0
num += tablebases.open_directory(os.path.join(os.path.dirname(__file__), "four-men"))
num += tablebases.open_directory(os.path.join(os.path.dirname(__file__), "five-men"))
num += tablebases.open_directory(os.path.join(os.path.dirname(__file__), "six-men", "wdl"), load_dtz=False)
num += tablebases.open_directory(os.path.join(os.path.dirname(__file__), "six-men", "dtz"), load_wdl=False)
app.logger.info("Loaded %d tablebase files.", num)


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


def jsonp(func):
    """Wraps JSONified output for JSONP requests."""
    @functools.wraps(func)
    def decorated_function(*args, **kwargs):
        callback = request.args.get('callback', False)
        if callback:
            data = str(func(*args, **kwargs).data)
            content = str(callback) + '(' + data + ');'
            mimetype = 'application/javascript'
            return current_app.response_class(content, mimetype=mimetype)
        else:
            return func(*args, **kwargs)
    return decorated_function


def probe(board):
    moves = {}

    # The best move will be determined in this order.
    mating_move = None
    zeroing_move = None
    winning_move, winning_dtz = None, -9999
    stalemating_move = None
    insuff_material_move = None
    drawing_move = None
    losing_move, losing_dtz = None, -9999
    losing_zeroing_move, losing_zeroing_dtz = None, -9999

    # Look at all moves and probe for the result position.
    for move in board.legal_moves:
        uci_move = board.uci(move, chess960=False)
        board.push(move)

        moves[uci_move] = dtz = tablebases.probe_dtz(board)

        # Mate.
        if board.is_checkmate():
            mating_move = uci_move

        # Winning zeroing move.
        if dtz is not None and dtz < 0 and board.halfmove_clock == 0:
            zeroing_move = uci_move

        # Winning move.
        if dtz is not None and dtz < 0 and dtz > winning_dtz:
            winning_move = uci_move
            winning_dtz = dtz

        # Stalemating move.
        if board.is_stalemate():
            stalemating_move = uci_move

        # Insufficient material.
        if board.is_insufficient_material():
            insuff_material_move = uci_move

        # Drawing move.
        if dtz is not None and dtz == 0:
            drawing_move = uci_move

        # Losing move.
        if dtz is not None and board.halfmove_clock != 0 and dtz > losing_dtz:
            losing_move = uci_move
            losing_dtz = dtz

        # Losing move.
        if dtz is not None and dtz > losing_zeroing_dtz:
            losing_zeroing_move = uci_move
            losing_zeroing_dtz = dtz

        board.pop()

    return {
        "dtz": tablebases.probe_dtz(board),
        "wdl": tablebases.probe_wdl(board),
        "bestmove": mating_move or zeroing_move or winning_move or stalemating_move or insuff_material_move or drawing_move or losing_move or losing_zeroing_move,
        "moves": moves,
    }


@app.route("/api")
@jsonp
def api():
    # Get required fen argument.
    fen = request.args.get("fen")
    if not fen:
        return abort(400)

    # Setup a board with the given FEN or EPD.
    try:
        board = chess.Board(fen)
    except ValueError:
        return abort(400)

    # Check the position for validity.
    if not board.is_valid(allow_chess960=False):
        return abort(400)

    return jsonify(**probe(board))


@app.route("/")
def index():
    # Setup a board from the given valid FEN or fall back to the default FEN.
    try:
        board = chess.Board(request.args.get("fen", DEFAULT_FEN))
    except ValueError:
        try:
            board = chess.Board()
            board.set_epd(request.args.get("fen", DEFAULT_FEN))
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

    if not board.is_valid(allow_chess960=False):
        status = "Invalid position"
    elif board.fen() == DEFAULT_FEN:
        status = "Draw by insufficient material"
        wdl = 0
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
        wdl = tablebases.probe_wdl(board)
        dtz = tablebases.probe_dtz(board)
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
            uci = board.uci(move, chess960=False)
            board.push(move)

            move_info = {
                "uci": uci,
                "san": san,
                "fen": board.epd() + " 0 1",
                "dtz": tablebases.probe_dtz(board),
                "zeroing": board.halfmove_clock == 0,
                "checkmate": board.is_checkmate(),
                "stalemate": board.is_stalemate(),
                "insufficient_material": board.is_insufficient_material(),
            }

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
    winning_moves.sort(key=lambda move: move["dtz"], reverse=True)
    winning_moves.sort(key=lambda move: move["zeroing"], reverse=True)
    winning_moves.sort(key=lambda move: move["checkmate"], reverse=True)

    drawing_moves.sort(key=lambda move: move["uci"])
    drawing_moves.sort(key=lambda move: move["insufficient_material"], reverse=True)
    drawing_moves.sort(key=lambda move: move["stalemate"], reverse=True)

    losing_moves.sort(key=lambda move: move["uci"])
    losing_moves.sort(key=lambda move: move["dtz"], reverse=True)
    losing_moves.sort(key=lambda move: move["zeroing"])

    return html_minify(render_template("index.html",
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
        illegal=not board.is_valid(allow_chess960=False),
        not_yet_solved=board.epd() + " 0 1" == chess.STARTING_FEN,
        unknown=wdl is None,
        turn="white" if board.turn == chess.WHITE else "black",
        white_fen=white_fen,
        black_fen=black_fen,
        horizontal_fen=mirror_horizontal(fen),
        vertical_fen=mirror_vertical(fen),
        swapped_fen=swap_colors(fen),
        DEFAULT_FEN=DEFAULT_FEN,
        material=material(board)
    ))


@app.route("/legal")
def imprint():
    return html_minify(render_template("legal.html"))


@app.route("/apidoc")
def apidoc():
    render = {}
    render["DEFAULT_FEN"] = DEFAULT_FEN
    render["status"] = 200

    # Parse the FEN.
    fen = request.args.get("fen")
    if not fen:
        render["status"] = 400
    else:
        try:
            board = chess.Board(fen)
        except ValueError:
            render["status"] = 400

    # Set the exact given FEN and a sanitized FEN for result.
    if fen is not None:
        render["fen"] = fen

    if render["status"] == 400:
        render["sanitized_fen"] = "8/8/8/8/8/8/8/8 w - - 0 1"
    else:
        render["sanitized_fen"] = board.fen()
        if board.is_valid(allow_chess960=False):
            render["request_body"] = json.dumps(probe(board), indent=2, sort_keys=True)
        else:
            render["status"] = 400

    # Render.
    return html_minify(render_template("apidoc.html", **render))


@app.route("/favicon.ico")
def favicon():
    return send_from_directory(app.root_path, "favicon.ico", mimetype="image/vnd.microsoft.icon")


@app.route("/sitemap.txt")
def sitemap():
    entries = [
        "",
        "?fen=6N1/5KR1/2n5/8/8/8/2n5/1k6%20w%20-%20-%200%201",
        "?fen=4r3/1K6/8/8/5p2/3k4/8/7Q%20b%20-%20-%200%201",
        "apidoc?fen=6N1/5KR1/2n5/8/8/8/2n5/1k6%20w%20-%20-%200%201",
        "legal",
    ]

    return current_app.response_class("\n".join("https://syzygy-tables.info/" + entry for entry in entries), mimetype="text/plain")


if __name__ == "__main__":
    try:
        import tornado
        import tornado.httpserver
        import tornado.wsgi
        import tornado.ioloop
    except ImportError:
        warnings.warn("Using builtin webserver, tornado not imported.")
        app.run()
    else:
        http_server = tornado.httpserver.HTTPServer(tornado.wsgi.WSGIContainer(app))
        http_server.listen(5000)
        tornado.ioloop.IOLoop.instance().start()
