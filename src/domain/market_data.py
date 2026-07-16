from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class MarketData:
    """
    Normalized market data object.

    Every exchange adapter must convert raw exchange
    responses into this unified structure.
    """

    symbol: str

    price: float

    bid: float

    ask: float

    volume: float

    timestamp: datetime

    @property
    def spread(self) -> float:
        return self.ask - self.bid

    @property
    def mid_price(self) -> float:
        return (self.ask + self.bid) / 2