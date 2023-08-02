#!/usr/bin/python3

import json
import re

import chess.syzygy

from _ctypes import PyObj_FromPtr


class NoIndent:
    def __init__(self, value):
        self.value = value


class JsonEncoder(json.JSONEncoder):
    # https://stackoverflow.com/a/13252112/722291

    FORMAT_SPEC = "@@{}@@"
    regex = re.compile(FORMAT_SPEC.format("(\d+)"))

    def __init__(self, **kwargs):
        self.__sort_keys = kwargs.get("sort_keys", None)
        super().__init__(**kwargs)

    def default(self, obj):
        return (self.FORMAT_SPEC.format(id(obj)) if isinstance(obj, NoIndent)
                else super().default(obj))

    def encode(self, obj):
        format_spec = self.FORMAT_SPEC
        json_repr = super().encode(obj)

        for match in self.regex.finditer(json_repr):
            id = int(match.group(1))
            no_indent = PyObj_FromPtr(id)
            json_obj_repr = json.dumps(no_indent.value, sort_keys=self.__sort_keys)

            json_repr = json_repr.replace(
                            '"{}"'.format(format_spec.format(id)), json_obj_repr)

        return json_repr


def main():
    with open("stats.json") as f:
        stats = json.load(f)

    sizes = {}
    for line in open("checksums/bytes.tsv"):
        b, filename = line.strip().split()
        sizes[filename] = int(b)

    internal = {}
    for line in open("checksums/tbcheck.txt"):
        filename, h = line.strip().split(": ")
        internal[filename] = h

    checksums = {"md5": {}, "sha1": {}, "sha256": {}, "sha512": {}, "b2": {}}
    for algo in checksums:
        for line in open(f"checksums/{algo}"):
            h, filename = line.strip().split()
            checksums[algo][filename] = h

    result = {}

    def sort_key(endgame):
        w, b = endgame.split("v", 1)
        return len(endgame), len(w), [-chess.syzygy.PCHR.index(p) for p in w], len(b), [-chess.syzygy.PCHR.index(p) for p in b]

    for table in sorted(chess.syzygy.tablenames(piece_count=7), key=sort_key):
        result[table] = {
            "rtbw": {
                "bytes": sizes[f"{table}.rtbw"],
                "tbcheck": internal[f"{table}.rtbw"],
                "md5": checksums["md5"][f"{table}.rtbw"],
                "sha1": checksums["sha1"][f"{table}.rtbw"],
                "sha256": checksums["sha256"][f"{table}.rtbw"],
                "sha512": checksums["sha512"][f"{table}.rtbw"],
                "b2": checksums["b2"][f"{table}.rtbw"],
            },
            "rtbz": {
                "bytes": sizes[f"{table}.rtbz"],
                "tbcheck": internal[f"{table}.rtbz"],
                "md5": checksums["md5"][f"{table}.rtbz"],
                "sha1": checksums["sha1"][f"{table}.rtbz"],
                "sha256": checksums["sha256"][f"{table}.rtbz"],
                "sha512": checksums["sha512"][f"{table}.rtbz"],
                "b2": checksums["b2"][f"{table}.rtbz"],
            },
            "longest": stats[table]["longest"],
            "histogram": {
                "white": {
                    "win": NoIndent(stats[table]["w"]["win_hist"]),
                    "loss": NoIndent(stats[table]["w"]["loss_hist"]),
                    "wdl": stats[table]["w"]["wdl"],
                },
                "black": {
                    "win": NoIndent(stats[table]["b"]["win_hist"]),
                    "loss": NoIndent(stats[table]["b"]["loss_hist"]),
                    "wdl": stats[table]["b"]["wdl"],
                },
            },
        }

    return result


if __name__ == "__main__":
    print(json.dumps(main(), indent=2, cls=JsonEncoder))
