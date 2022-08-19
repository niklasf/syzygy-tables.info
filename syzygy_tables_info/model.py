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

import dataclasses
import typing

from typing import List, Optional


try:
    from typing import Literal
    ColorName = Literal["white", "black"]
except ImportError:
    ColorName = str  # type: ignore


DEFAULT_FEN = "4k3/8/8/8/8/8/8/4K3 w - - 0 1"

EMPTY_FEN = "8/8/8/8/8/8/8/8 w - - 0 1"


try:
    class RenderMove(typing.TypedDict):
        san: str
        uci: str
        fen: str
        dtm: Optional[int]
        badge: str

        dtz: int
        zeroing: bool
        capture: bool
        checkmate: bool
        insufficient_material: bool
        stalemate: bool
except AttributeError:
    RenderMove = dict  # type: ignore


try:
    class RenderDep(typing.TypedDict):
        material: str
        longest_fen: str
except AttributeError:
    RenderDep = dict  # type: ignore


try:
    class RenderStatsLongest(typing.TypedDict):
        label: str
        fen: str
except AttributeError:
    RenderStatsLongest = dict  # type: ignore


try:
    class RenderStatsHist(typing.TypedDict, total=False):
        empty: int

        ply: int
        num: int
        width: int
        active: bool
except AttributeError:
    RenderStatsHist = dict  # type: ignore


try:
    class RenderStats(typing.TypedDict, total=False):
        material_side: str
        material_other: str

        white: int
        cursed: int
        draws: int
        blessed: int
        black: int

        white_pct: float
        cursed_pct: float
        draws_pct: float
        blessed_pct: float
        black_pct: float

        longest: List[RenderStatsLongest]
        verb: str  # winning, losing

        histogram: List[RenderStatsHist]
except AttributeError:
    RenderStats = dict  # type: ignore


try:
    class Render(typing.TypedDict, total=False):
        material: str
        normalized_material: str
        thumbnail_url: str
        turn: ColorName
        fen: str
        white_fen: str
        black_fen: str
        clear_fen: str
        swapped_fen: str
        horizontal_fen: str
        vertical_fen: str
        fen_input: str

        status: str
        dtz: Optional[int]
        dtm: Optional[int]
        winning_side: Optional[ColorName]
        frustrated: bool
        winning_moves: List[RenderMove]
        cursed_moves: List[RenderMove]
        drawing_moves: List[RenderMove]
        unknown_moves: List[RenderMove]
        blessed_moves: List[RenderMove]
        losing_moves: List[RenderMove]
        illegal: bool
        insufficient_material: bool
        blessed_loss: bool
        cursed_win: bool
        is_table: bool
        deps: List[RenderDep]
        stats: Optional[RenderStats]
except AttributeError:
    Render = dict  # type: ignore
