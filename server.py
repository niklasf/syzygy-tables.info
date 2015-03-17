#!/usr/bin/python2

from flask import Flask
from flask import render_template
from flask import current_app
from flask import request
from flask import abort
from flask import jsonify

import chess
import chess.syzygy

import functools
import os.path


DEFAULT_FEN = "4k3/8/8/8/8/8/8/4K3 w - - 0 1"


app = Flask(__name__)

tablebases = chess.syzygy.Tablebases()
tablebases.open_directory(os.path.join(os.path.dirname(__file__), "syzygy"))

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


@app.route("/api")
@jsonp
def api():
    # Get required fen argument.
    fen = request.args.get("fen")
    if not fen:
        return abort(400)

    # Setup a board with the given FEN or EPD.
    try:
        board = chess.Bitboard(fen)
    except ValueError:
        try:
            board = chess.Bitboard()
            board.set_epd(fen)
        except ValueError:
            return abort(400)

    # Check the position for validity.
    if board.status() != chess.STATUS_VALID:
        return abort(400)

    moves = {}

    # The best move will be determined in this order.
    mating_move = None
    zeroing_move = None
    winning_move, winning_dtz = None, -9999
    stalemating_move = None
    insuff_material_move = None
    drawing_move = None
    losing_move, losing_dtz = None, -9999

    # Look at all moves and probe for the result position.
    for move in board.legal_moves:
        board.push(move)

        moves[move.uci()] = dtz = tablebases.probe_dtz(board)

        # Mate.
        if board.is_checkmate():
            mating_move = move.uci()

        # Winning zeroing move.
        if dtz is not None and dtz < 0 and board.halfmove_clock == 0:
            zeroing_move = move.uci()

        # Winning move.
        if dtz is not None and dtz < 0 and dtz > winning_dtz:
            winning_move = move.uci()
            winning_dtz = dtz

        # Stalemating move.
        if board.is_stalemate():
            stalemating_move = move.uci()

        # Insufficient material.
        if board.is_insufficient_material():
            insuff_material_move = move.uci()

        # Drawing move.
        if dtz is not None and dtz == 0:
            drawing_move = move.uci()

        # Losing move.
        if dtz is not None and dtz > losing_dtz:
            losing_move = move.uci()
            losing_dtz = dtz

        board.pop()

    return jsonify(
        wdl=tablebases.probe_wdl(board),
        dtz=tablebases.probe_dtz(board),
        moves=moves,
        bestmove=mating_move or zeroing_move or winning_move or stalemating_move or insuff_material_move or drawing_move or losing_move)


@app.route("/")
def index():
    # Setup a board from the given valid FEN or fall back to the default FEN.
    try:
        board = chess.Bitboard(request.args.get("fen", DEFAULT_FEN))
    except ValueError:
        try:
            board = chess.Bitboard()
            board.set_epd(request.args.get("fen", DEFAULT_FEN))
        except ValueError:
            board = chess.Bitboard(DEFAULT_FEN)

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

    if board.status() != chess.STATUS_VALID:
        status = "Invalid position"
    elif board.is_insufficient_material():
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
        dtz = tablebases.probe_dtz(board)
        if dtz is None:
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
            board.push(move)

            move_info = {
                "uci": move.uci(),
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
                    move_info["badge"] = "Win with DTZ %d" % (abs(dtz), )

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
                else:
                    move_info["badge"] = "Loss with DTZ %d" % (abs(dtz), )
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

    return render_template("index.html",
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
        illegal=board.status() != chess.STATUS_VALID,
        not_yet_solved=board.epd() + " 0 1" == chess.STARTING_FEN,
        unknown=wdl is None,
        turn="white" if board.turn == chess.WHITE else "black",
        white_fen=white_fen,
        black_fen=black_fen,
        horizontal_fen=mirror_horizontal(fen),
        vertical_fen=mirror_vertical(fen),
        swapped_fen=swap_colors(fen),
        DEFAULT_FEN=DEFAULT_FEN
    )

@app.route("/legal")
def imprint():
    return render_template("legal.html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True)
