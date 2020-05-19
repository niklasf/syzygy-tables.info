#!/usr/bin/python3

import sys
import chess.syzygy

def sort_key(item):
    _, filename = item
    #filename, _ = item
    endgame, ext = filename.split(".")
    w, b = endgame.split("v", 1)
    return len(endgame), len(w), [-chess.syzygy.PCHR.index(p) for p in w], len(b), [-chess.syzygy.PCHR.index(p) for p in b], ".rtbz" in filename

tables = []
for line in open(sys.argv[1]):
    tables.append(line.strip().split(
    #": "
    ))

tables.sort(key=sort_key)
for s, name in tables:
    print(s, name,
    sep="  ",
    #sep="\t"
    )
