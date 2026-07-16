from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class Candle:

    symbol: str

    timeframe: str

    open: float

    high: float

    low: float

    close: float

    volume: float

    timestamp: datetime


class CandleBuilder:

    def __init__(self):

        self._current: Candle | None = None

    def start(
        self,
        symbol: str,
        timeframe: str,
        price: float,
        volume: float,
        timestamp: datetime,
    ) -> Candle:

        self._current = Candle(
            symbol=symbol,
            timeframe=timeframe,
            open=price,
            high=price,
            low=price,
            close=price,
            volume=volume,
            timestamp=timestamp,
        )

        return self._current

    def update(
        self,
        price: float,
        volume: float,
    ) -> Candle:

        candle = self._current

        if candle is None:
            raise RuntimeError("No active candle.")

        candle.high = max(candle.high, price)
        candle.low = min(candle.low, price)

        candle.close = price

        candle.volume += volume

        return candle

    @property
    def current(self):

        return self._current