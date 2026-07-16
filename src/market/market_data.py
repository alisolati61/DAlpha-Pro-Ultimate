from dataclasses import dataclass
from typing import Optional


@dataclass(slots=True)
class MarketData:
    symbol: str

    last_price: float

    bid: float

    ask: float

    volume: float

    timestamp: Optional[int] = None

    exchange: Optional[str] = None