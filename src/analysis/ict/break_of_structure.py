from __future__ import annotations

from src.analysis.ict.ict_engine import ICTModule
from src.analysis.signal_engine import Signal
from src.domain.candle_series import CandleSeries


class BreakOfStructureAnalyzer(ICTModule):
    """
    ICT Break Of Structure detector.
    """

    def analyze(
        self,
        series: CandleSeries,
    ) -> Signal:

        if len(series.candles) < 5:

            return Signal(
                direction="NEUTRAL",
                confidence=0,
                reason="Not enough candles",
            )

        candles = series.candles

        last = candles[-1]

        previous = candles[-2]

        highs = [c.high for c in candles[-5:-1]]

        lows = [c.low for c in candles[-5:-1]]

        highest = max(highs)

        lowest = min(lows)

        if last.close > highest:

            return Signal(
                direction="BUY",
                confidence=90,
                reason="Bullish BOS",
            )

        if last.close < lowest:

            return Signal(
                direction="SELL",
                confidence=90,
                reason="Bearish BOS",
            )

        return Signal(
            direction="NEUTRAL",
            confidence=0,
            reason="No BOS",
        )