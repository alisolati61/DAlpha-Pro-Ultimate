from __future__ import annotations

from src.analysis.ict.ict_engine import ICTModule
from src.analysis.signal_engine import Signal
from src.domain.candle_series import CandleSeries


class BreakerBlockAnalyzer(ICTModule):
    """
    ICT Breaker Block detector.
    """

    def analyze(
        self,
        series: CandleSeries,
    ) -> Signal:

        if len(series.candles) < 7:

            return Signal(
                direction="NEUTRAL",
                confidence=0,
                reason="Not enough candles",
            )

        candles = series.candles

        previous = candles[-2]

        current = candles[-1]

        if (
            current.close > previous.high
            and current.low > previous.low
        ):

            return Signal(
                direction="BUY",
                confidence=88,
                reason="Bullish Breaker Block",
            )

        if (
            current.close < previous.low
            and current.high < previous.high
        ):

            return Signal(
                direction="SELL",
                confidence=88,
                reason="Bearish Breaker Block",
            )

        return Signal(
            direction="NEUTRAL",
            confidence=0,
            reason="No Breaker Block",
        )