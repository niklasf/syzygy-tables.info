import json
import os.path

from typing import Dict, List, TypedDict


TableStats = TypedDict("TableStats", {
    "bytes": int,
    "tbcheck": str,
    "md5": str,
    "sha1": str,
    "sha256": str,
    "sha512": str,
    "sha3-224": str,
    "b2": str,
    "b3": str,
})


class LongEndgame(TypedDict):
    epd: str
    ply: int
    wdl: int


class Histogram(TypedDict):
    win: List[int]
    loss: List[int]
    wdl: Dict[str, int]


class Histograms(TypedDict):
    white: Histogram
    black: Histogram


class EndgameStats(TypedDict):
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
