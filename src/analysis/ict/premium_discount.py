from __future__ import annotations

from src.analysis.ict.ict_engine import ICTModule
from src.analysis.signal_engine import Signal
from src.domain.candle_series import CandleSeries


class PremiumDiscountAnalyzer(ICTModule):
    """
    ICT Premium / Discount Zone detector.
    """

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

        midpoint = (highest + lowest) / 2

        last = candles[-1]

        if last.close < midpoint:

            return Signal(
                direction="BUY",
                confidence=84,
                reason="Discount Zone",
            )

        if last.close > midpoint:

            return Signal(
                direction="SELL",
                confidence=84,
                reason="Premium Zone",
            )

        return Signal(
            direction="NEUTRAL",
            confidence=0,
            reason="Equilibrium",
        )