from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(slots=True)
class Candle:

    symbol: str

    timeframe: str

    open: float

    high: float

    low: float

    close: float

    volume: float

    start_time: datetime


class CandleBuilder:

    """
    Builds OHLCV candles from incoming ticks.

    Future
    -------
    - Multi-timeframe aggregation
    - Volume Profile
    - VWAP
    """

    def __init__(self) -> None:

        self._current: dict[
            tuple[str, str],
            Candle,
        ] = {}

    # ------------------------------------------------

    def update(

        self,

        symbol: str,

        timeframe: str,

        price: float,

        volume: float,

        timestamp: datetime | None = None,

    ) -> Candle:

        if timestamp is None:

            timestamp = datetime.now(UTC)

        key = (

            symbol,

            timeframe,

        )

        if key not in self._current:

            candle = Candle(

                symbol=symbol,

                timeframe=timeframe,

                open=float(price),

                high=float(price),

                low=float(price),

                close=float(price),

                volume=float(volume),

                start_time=timestamp,

            )

            self._current[key] = candle

            return candle

        candle = self._current[key]

        candle.high = max(
            candle.high,
            float(price),
        )

        candle.low = min(
            candle.low,
            float(price),
        )

        candle.close = float(price)

        candle.volume += float(volume)

        return candle

    # ------------------------------------------------

    def latest(

        self,

        symbol: str,

        timeframe: str,

    ) -> Candle | None:

        return self._current.get(

            (

                symbol,

                timeframe,

            )

        )

    # ------------------------------------------------

    def clear(self) -> None:

        self._current.clear()