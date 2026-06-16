import time
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class PositionStatus(Enum):
    OPEN = "open"
    CLOSED = "closed"
    PARTIAL = "partial"
    PENDING = "pending"
    FAILED = "failed"


@dataclass
class Position:
    exchange_id: str
    symbol: str
    market_symbol: str
    side: str
    entry_price: float
    amount: float
    leverage: int
    sl_order_id: Optional[str] = None
    sl_price: float = 0.0
    tp_order_ids: List[str] = field(default_factory=list)
    entry_order_ids: List[str] = field(default_factory=list)
    open_time: float = 0.0
    status: PositionStatus = PositionStatus.OPEN
    pnl: float = 0.0
    tp1_hit: bool = False
    is_breakeven: bool = False
    highest_price: float = 0.0
    lowest_price: float = 0.0
    trailing_activated: bool = False
    entry_filled_amount: float = 0.0
    exit_price: Optional[float] = None
    close_time: Optional[float] = None

    def __post_init__(self):
        if self.open_time == 0.0:
            self.open_time = time.time()
        if isinstance(self.status, str):
            self.status = PositionStatus(self.status)


@dataclass
class Signal:
    symbol: str
    direccion: str
    entry_min: Optional[float] = None
    entry_max: Optional[float] = None
    stop_loss: Optional[float] = None
    targets: List[float] = field(default_factory=list)
    raw_text: str = ""

    def __post_init__(self):
        if len(self.raw_text) > 1000:
            self.raw_text = self.raw_text[:1000] + "..."
