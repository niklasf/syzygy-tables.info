#!/usr/bin/python2

from flask import Flask
from flask import render_template
from flask import request
from flask import abort
from flask import jsonify

import os.path

import chess
import chess.syzygy

app = Flask(__name__)

DEFAULT_FEN = "4k3/8/8/8/8/8/8/4K3 w - - 0 1"

tablebases = chess.syzygy.Tablebases()
tablebases.open_directory(os.path.join(os.path.dirname(__file__), "syzygy"))

@app.route("/api")
def api():
    fen = request.args.get("fen")
    if not fen:
        return abort(400)

    try:
        board = chess.Bitboard(fen)
    except ValueError:
        try:
            board = chess.Bitboard()
            board.set_epd(fen)
        except ValueError:
            return abort(400)

    if board.status() != chess.STATUS_VALID:
        return abort(400)

    moves = {}

    bestmove = None
    best_winning_dtz = -9999
    best_losing_dtz = 9999
    best_result = -4

    for move in board.legal_moves:
        board.push(move)

        moves[move.uci()] = dtz = tablebases.probe_dtz(board)

        if board.is_checkmate():
            bestmove = move.uci()
            best_result = 3

        if dtz is not None:
            if best_result <= 2 and dtz < 0 and board.halfmove_clock == 0:
                bestmove = move.uci()
                best_result = 2

            if best_result <= 1 and dtz < 0 and dtz > best_winning_dtz:
                bestmove = move.uci()
                best_result = 1
                best_winning_dtz = dtz

        if best_result <= 0 and board.is_stalemate():
            bestmove = move.uci()
            best_result = 0

        if best_result <= -1 and board.is_insufficient_material():
            bestmove = move.uci()
            best_result = -1

        if dtz is not None:
            if best_result <= -2 and dtz == 0:
                bestmove = move.uci()
                best_result = -2

            if best_result <= -3 and dtz < best_losing_dtz:
                bestmove = move.uci()
                best_result = -3
                best_losing_dtz = dtz

        board.pop()

    return jsonify(
        wdl=tablebases.probe_wdl(board),
        dtz=tablebases.probe_dtz(board),
        moves=moves,
        bestmove=bestmove)

@app.route("/")
def query_page():
    try:
        board = chess.Bitboard(request.args.get("fen", DEFAULT_FEN))
    except ValueError:
        try:
            board = chess.Bitboard()
            board.set_epd(request.args.get("fen", DEFAULT_FEN))
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
    wdl = None

    if board.status() != chess.STATUS_VALID:
        status = "Invalid position"
    elif board.is_insufficient_material():
        wdl = 0
        status = "Draw by insufficient material"
    elif board.is_stalemate():
        status = "Draw by stalemate"
        wdl = 0
    elif board.is_checkmate():
        wdl = 2
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

        fallback_wdl = wdl = tablebases.probe_wdl(board)
        if fallback_wdl is None:
            fallback_wdl = -2

        for move in board.legal_moves:
            san = board.san(move)

            board.push(move)

            next_fen = board.epd() + " 0 1"

            dtz = tablebases.probe_dtz(board)

            if board.is_checkmate() or ((dtz is not None) and dtz < 0):
                if board.is_checkmate():
                    badge = "Checkmate"
                elif dtz is None:
                    badge = "Unknown"
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
            elif board.is_stalemate() or board.is_insufficient_material() or (dtz == 0 or (dtz is None and fallback_wdl < 0)):
                if board.is_stalemate():
                    badge = "Stalemate"
                elif board.is_insufficient_material():
                    badge = "Insufficient material"
                elif dtz == 0:
                    badge = "Draw"
                else:
                    badge = "Unknown"

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
        insufficient_material=board.is_insufficient_material(),
        winning_side=winning_side,
        losing_side=losing_side,
        winning_moves=winning_moves,
        drawing_moves=drawing_moves,
        blessed_loss=wdl == -1,
        cursed_win=wdl == 1,
        illegal=board.status() != chess.STATUS_VALID,
        not_yet_solved=board.epd() + " 0 1" == chess.STARTING_FEN,
        unknown=wdl is None,
        turn=turn,
        losing_moves=losing_moves,
        white_fen=white_fen,
        black_fen=black_fen,
        DEFAULT_FEN=DEFAULT_FEN
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True)
