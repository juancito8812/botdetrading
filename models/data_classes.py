import time
from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class Position:
    exchange_id: str
    symbol: str
    market_symbol: str
    side: str  # 'Buy' o 'Sell'
    entry_price: float
    amount: float
    leverage: int
    sl_order_id: Optional[str] = None
    tp_order_ids: List[str] = field(default_factory=list)
    entry_order_ids: List[str] = field(default_factory=list)
    open_time: str = field(default_factory=lambda: time.strftime("%Y-%m-%d %H:%M:%S"))
    status: str = "open"  # 'open', 'pending', 'closed', 'failed'
    pnl: float = 0.0
    tp1_hit: bool = False
    is_breakeven: bool = False
    highest_price: float = 0.0
    lowest_price: float = 0.0
    trailing_activated: bool = False
    entry_filled_amount: float = 0.0

@dataclass
class Signal:
    simbolo: str
    direccion: str  # 'Buy' o 'Sell'
    entry_min: Optional[float] = None
    entry_max: Optional[float] = None
    stop_loss: Optional[float] = None
    targets: List[float] = field(default_factory=list)
    raw_text: str = ""
