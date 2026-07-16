from __future__ import annotations

from src.analysis.ict.ict_engine import ICTModule
from src.analysis.signal_engine import Signal
from src.domain.candle_series import CandleSeries


class ChangeOfCharacterAnalyzer(ICTModule):
    """
    ICT Change Of Character detector.
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

        previous = candles[-6:-1]

        last = candles[-1]

        highest = max(c.high for c in previous)

        lowest = min(c.low for c in previous)

        if last.close > highest:

            return Signal(
                direction="BUY",
                confidence=95,
                reason="Bullish CHOCH",
            )

        if last.close < lowest:

            return Signal(
                direction="SELL",
                confidence=95,
                reason="Bearish CHOCH",
            )

        return Signal(
            direction="NEUTRAL",
            confidence=0,
            reason="No CHOCH",
        )