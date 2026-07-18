from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(slots=True)
class MarketData:
    """
    Unified market snapshot shared across the system.
    """

    symbol: str

    exchange: str

    timeframe: str

    price: float

    bid: float

    ask: float

    volume: float

    timestamp: datetime

    spread: float = 0.0

    def __post_init__(self) -> None:

        self.price = float(self.price)

        self.bid = float(self.bid)

        self.ask = float(self.ask)

        self.volume = float(self.volume)

        self.spread = float(self.ask - self.bid)

        if self.timestamp.tzinfo is None:

            self.timestamp = self.timestamp.replace(
                tzinfo=UTC,
            )