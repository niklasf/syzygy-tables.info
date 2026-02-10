from typing import List, Literal, Optional, TypedDict, NotRequired


ColorName = Literal["white", "black"]


DEFAULT_FEN = "4k3/8/8/8/8/8/8/4K3 w - - 0 1"

EMPTY_FEN = "8/8/8/8/8/8/8/8 w - - 0 1"


ApiCategory = Literal[
    "win",
    "unknown",
    "syzygy-win",
    "maybe-win",
    "cursed-win",
    "draw",
    "blessed-loss",
    "maybe-loss",
    "syzygy-loss",
    "loss",
]


class ApiMove(TypedDict):
    uci: str
    san: str
    category: ApiCategory
    dtz: NotRequired[int]
    precise_dtz: NotRequired[int]
    dtc: NotRequired[int]
    dtm: NotRequired[int]
    zeroing: NotRequired[bool]
    conversion: NotRequired[bool]
    checkmate: NotRequired[bool]
    stalemate: NotRequired[bool]
    insufficient_material: NotRequired[bool]


class ApiResponse(TypedDict):
    category: ApiCategory
    dtz: NotRequired[int]
    precise_dtz: NotRequired[int]
    dtc: NotRequired[int]
    dtm: NotRequired[int]
    checkmate: NotRequired[bool]
    stalemate: NotRequired[bool]
    insufficient_material: NotRequired[bool]
    moves: List[ApiMove]


class RenderMove(TypedDict):
    uci: str
    san: str
    fen: str
    wdl: Optional[int]

    checkmate: bool
    stalemate: bool
    insufficient_material: bool
    zeroing: bool
    capture: bool

    dtz: Optional[int]
    dtm: Optional[int]

    badge: str


class RenderDep(TypedDict):
    material: str
    longest_fen: str


class RenderStatsLongest(TypedDict):
    label: str
    fen: str


class RenderStatsHist(TypedDict, total=False):
    empty: int

    ply: int
    num: int
    width: int
    active: bool


class RenderStats(TypedDict, total=False):
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


class Render(TypedDict, total=False):
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

    tarpit: Optional[str]
