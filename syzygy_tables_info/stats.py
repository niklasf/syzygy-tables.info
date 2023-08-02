import json
import os.path
import typing

from typing import Dict, List


class TableStats(typing.TypedDict):
    bytes: int
    tbcheck: str
    md5: str
    sha1: str
    sha256: str
    sha512: str
    b2: str


class LongEndgame(typing.TypedDict):
    epd: str
    ply: int
    wdl: int


class Histogram(typing.TypedDict):
    win: List[int]
    loss: List[int]
    wdl: Dict[str, int]


class Histograms(typing.TypedDict):
    white: Histogram
    black: Histogram


class EndgameStats(typing.TypedDict):
    rtbw: TableStats
    rtbz: TableStats
    longest: List[LongEndgame]
    histogram: Histograms


def longest_fen(material: str) -> str:
    if material == "KNvK":
        return "4k3/8/8/8/8/8/8/1N2K3 w - - 0_1"
    elif material == "KBvK":
        return "4k3/8/8/8/8/8/8/2B1K3 w - - 0 1"
    else:
        stats = STATS[material]
        longest = max(stats["longest"], key=lambda e: e["ply"])
        return longest["epd"] + " 0 1"


def is_maximal(material: str) -> bool:
    return material in ["KRvK", "KBNvK", "KNNvKP", "KRNvKNN", "KRBNvKQN"]


with open(os.path.join(os.path.dirname(__file__), "..", "stats.json")) as f:
    STATS: Dict[str, EndgameStats] = json.load(f)
