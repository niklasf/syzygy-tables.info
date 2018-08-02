#!/usr/bin/env python

import sys
import json


def process(f):
    eg, side, data = None, "w", None

    for line in f.readlines():
        line = line.strip()
        if line.startswith("###"):
            if eg is not None:
                yield eg, data

            _, eg, _ = line.split(None, 2)
            data = {
                "w": {
                    "win_hist": [], # Histogram of wins
                    "loss_hist": [], # Histogram of losses
                    "wdl": {-2: 0, -1: 0, 0: 0, 1: 0, 2: 0},
                },
                "b": {
                    "win_hist": [],
                    "loss_hist": [],
                    "wdl": {-2: 0, -1: 0, 0: 0, 1: 0, 2: 0},
                },
                "longest": [],
            }
        elif "White to move" in line:
            side = "w"
        elif "Black to move" in line:
            side = "b"
        elif "positions win in" in line:
            num, _, _, _, ply, _ = line.split(None, 5)
            set_ply(data[side]["win_hist"], int(ply), int(num))
        elif "positions lose in" in line:
            num, _, _, _, ply, _ = line.split(None, 5)
            set_ply(data[side]["loss_hist"], int(ply), int(num))
        elif "positions are wins" in line:
            num, _ = line.split(None, 1)
            data[side]["wdl"][2] = int(num)
        elif "positions are cursed wins" in line:
            num, _ = line.split(None, 1)
            data[side]["wdl"][1] = int(num)
        elif "positions are losses" in line:
            num, _ = line.split(None, 1)
            data[side]["wdl"][-1] = int(num)
        elif "positions are cursed losses" in line:
            num, _ = line.split(None, 1)
            data[side]["wdl"][-2] = int(num)
        elif "positions are draws" in line:
            num, _ = line.split(None, 1)
            data[side]["wdl"][0] = int(num)
        elif "Longest" in line:
            label, desc = line.split(": ", 1)
            ply, _, epd = desc.split(None, 2)
            ply = int(ply)
            if (" w " in epd) == ("win for white" in label):
                wdl = 1
            else:
                wdl = -1
            if "cursed" not in label:
                wdl *= 2
            data["longest"].append({
                "epd": epd,
                "ply": ply,
                "wdl": wdl,
            })

    if eg is not None:
        yield eg, data

def set_ply(h, ply, num):
    while len(h) <= ply:
        h.append(0)
    h[ply] = num

def main(args):
    result = {}
    for arg in args:
        with open(arg) as f:
            for eg, data in process(f):
                result[eg] = data
    return result


if __name__ == "__main__":
    print(json.dumps(main(sys.argv[1:])))
