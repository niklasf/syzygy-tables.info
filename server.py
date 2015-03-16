#!/usr/bin/python2

from flask import Flask
from flask import render_template
from flask import request

import chess
import chess.syzygy

app = Flask(__name__)

DEFAULT_FEN = "4k3/8/8/8/8/8/8/4K3 w - - 0 1"

tablebases = chess.syzygy.Tablebases()
tablebases.open_directory("/home/niklas/Projekte/python-chess/data/syzygy")

@app.route("/")
def query_page():
    try:
        board = chess.Bitboard(request.args.get("fen", DEFAULT_FEN))
    except ValueError:
        board = chess.Bitboard(DEFAULT_FEN)

    original_turn = board.turn
    board.turn = chess.WHITE
    white_fen = board.fen()
    board.turn = chess.BLACK
    black_fen = board.fen()
    board.turn = original_turn

    winning_side = "no"
    losing_side = "no"
    turn = "white" if board.turn == chess.WHITE else "black"
    winning_moves = []
    drawing_moves = []
    losing_moves = []

    if board.status() != chess.STATUS_VALID:
        status = "Invalid position"
    if board.is_insufficient_material():
        status = "Draw by insufficient material"
    elif board.is_stalemate():
        status = "Draw by stalemate"
    elif board.is_checkmate():
        if board.turn == chess.WHITE:
            status = "Black won by checkmate"
            winning_side = "black"
            losing_side = "white"
        else:
            status = "White won by checkmate"
            winning_side = "white"
            losing_side = "black"
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

        fallback_wdl = tablebases.probe_wdl(board)
        if fallback_wdl is None:
            fallback_wdl = -2

        for move in board.legal_moves:
            san = board.san(move)

            board.push(move)

            next_fen = board.epd() + " 0 1"

            dtz = tablebases.probe_dtz(board)

            if (dtz is not None and dtz < 0) or (dtz is None and fallback_wdl < 0):
                if dtz is None:
                    badge = "Unknown"
                elif board.is_checkmate():
                    badge = "Checkmate"
                elif board.halfmove_clock == 0:
                    badge = "Zeroing"
                else:
                    badge = "Win with DTZ %d" % (abs(dtz), )

                winning_moves.append({
                    "uci": move.uci(),
                    "fen": next_fen,
                    "san": san,
                    "badge": badge,
                    "zeroing": board.halfmove_clock == 0,
                    "checkmate": board.is_checkmate(),
                    "dtz": dtz,
                })
            elif dtz == 0:
                if board.is_stalemate():
                    badge = "Stalemate"
                elif board.is_insufficient_material():
                    badge = "Insufficient material"
                else:
                    badge = "Draw"

                drawing_moves.append({
                    "uci": move.uci(),
                    "fen": next_fen,
                    "san": san,
                    "badge": badge,
                    "stalemate": board.is_stalemate(),
                    "insufficient_material": board.is_insufficient_material(),
                })
            else:
                if dtz is None:
                    badge = "Unknown"
                else:
                    badge = "Loss with DTZ %d" % (abs(dtz), )

                losing_moves.append({
                    "uci": move.uci(),
                    "fen": next_fen,
                    "san": san,
                    "badge": badge,
                    "dtz": dtz
                })

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
        fen=board.epd() + " 0 1",
        status=status,
        winning_side=winning_side,
        losing_side=losing_side,
        winning_moves=winning_moves,
        drawing_moves=drawing_moves,
        turn=turn,
        losing_moves=losing_moves,
        white_fen=white_fen,
        black_fen=black_fen
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True)
