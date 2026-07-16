from __future__ import annotations

from src.analysis.ict.ict_engine import ICTModule
from src.analysis.signal_engine import Signal
from src.domain.candle_series import CandleSeries


class OptimalTradeEntryAnalyzer(ICTModule):
    """
    ICT Optimal Trade Entry (OTE).

    Foundation version based on the
    62%–79% Fibonacci retracement zone.
    """

    OTE_LOW = 0.62
    OTE_HIGH = 0.79

    def analyze(
        self,
        series: CandleSeries,
    ) -> Signal:

        if len(series.candles) < 20:

            return Signal(
                direction="NEUTRAL",
                confidence=0,
                reason="Not enough candles",
            )

        candles = series.candles[-20:]

        highest = max(c.high for c in candles)

        lowest = min(c.low for c in candles)

        last = candles[-1]

        fib_range = highest - lowest

        if fib_range <= 0:

            return Signal(
                direction="NEUTRAL",
                confidence=0,
                reason="Invalid range",
            )

        bullish_low = highest - fib_range * self.OTE_HIGH
        bullish_high = highest - fib_range * self.OTE_LOW

        bearish_low = lowest + fib_range * self.OTE_LOW
        bearish_high = lowest + fib_range * self.OTE_HIGH

        if bullish_low <= last.close <= bullish_high:

            return Signal(
                direction="BUY",
                confidence=90,
                reason="Bullish OTE Zone",
            )

        if bearish_low <= last.close <= bearish_high:

            return Signal(
                direction="SELL",
                confidence=90,
                reason="Bearish OTE Zone",
            )

        return Signal(
            direction="NEUTRAL",
            confidence=0,
            reason="Outside OTE",
        )