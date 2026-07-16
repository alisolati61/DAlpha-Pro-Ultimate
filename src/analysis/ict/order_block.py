from __future__ import annotations

from dataclasses import dataclass

from src.analysis.ict.ict_engine import ICTModule
from src.analysis.signal_engine import Signal
from src.domain.candle_series import CandleSeries


@dataclass(slots=True)
class OrderBlock:

    bullish: bool

    high: float

    low: float


class OrderBlockAnalyzer(ICTModule):
    """
    Simple ICT Order Block detector.
    """

    def analyze(
        self,
        series: CandleSeries,
    ) -> Signal:

        if len(series.candles) < 6:

            return Signal(
                direction="NEUTRAL",
                confidence=0,
                reason="Not enough candles",
            )

        candles = series.candles

        previous = candles[-2]

        current = candles[-1]

        if current.close > previous.high:

            return Signal(
                direction="BUY",
                confidence=90,
                reason="Bullish Order Block",
            )

        if current.close < previous.low:

            return Signal(
                direction="SELL",
                confidence=90,
                reason="Bearish Order Block",
            )

        return Signal(
            direction="NEUTRAL",
            confidence=0,
            reason="No Order Block",
        )