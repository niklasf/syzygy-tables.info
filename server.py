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

    winning_side = None
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
            winning_side="black"
        else:
            status = "White won by checkmate"
            winning_side="white"
    else:
        dtz = tablebases.probe_dtz(board)
        if dtz is None:
            status = "Position not found in tablebases"
        elif dtz == 0:
            status = "Tablebase draw"
        elif dtz > 0 and board.turn == chess.WHITE:
            status = "White is winning with DTZ %d" % (abs(dtz), )
            winning_side = "white"
        elif dtz < 0 and board.turn == chess.WHITE:
            status = "White is losing with DTZ %d" % (abs(dtz), )
            winning_side = "black"
        elif dtz > 0 and board.turn == chess.BLACK:
            status = "Black is winning with DTZ %d" % (abs(dtz), )
            winning_side = "black"
        elif dtz < 0 and board.turn == chess.BLACK:
            status = "Black is losing with DTZ %d" % (abs(dtz), )
            winning_side = "white"

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
        fen=board.fen() if board.fen() != DEFAULT_FEN else "",
        status=status,
        winning_side=winning_side,
        winning_moves=winning_moves,
        drawing_moves=drawing_moves,
        losing_moves=losing_moves
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True)
