# This file is part of the syzygy-tables.info tablebase probing website.
# Copyright (C) 2015-2020 Niklas Fiekas <niklas.fiekas@backscattering.de>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import annotations

import json
import os.path
import typing

from typing import Dict, List


try:
    class EndgameStats(typing.TypedDict):
        rtbw: TableStats
        rtbz: TableStats
        longest: List[LongEndgame]
        histogram: Histograms
except AttributeError:
    EndgameStats = dict  # type: ignore


try:
    class TableStats(typing.TypedDict):
        bytes: int
        tbcheck: str
        md5: str
        sha1: str
        sha256: str
        sha512: str
        b2: str
        ipfs: str
except AttributeError:
    TableStats = dict  # type: ignore


try:
    class Histograms(typing.TypedDict):
        white: Histogram
        black: Histogram
except AttributeError:
    Histograms = dict  # type: ignore


try:
    class Histogram(typing.TypedDict):
        win: List[int]
        loss: List[int]
        wdl: Dict[str, int]
except AttributeError:
    Histogram = dict  # type: ignore


try:
    class LongEndgame(typing.TypedDict):
        epd: str
        ply: int
        wdl: int
except AttributeError:
    LongEndgame = dict  # type: ignore


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
