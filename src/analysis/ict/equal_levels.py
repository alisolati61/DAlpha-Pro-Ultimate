from __future__ import annotations

from src.analysis.ict.ict_engine import ICTModule
from src.analysis.signal_engine import Signal
from src.domain.candle_series import CandleSeries


class EqualLevelsAnalyzer(ICTModule):
    """
    Detect Equal Highs and Equal Lows.
    """

    TOLERANCE = 0.001  # 0.1%

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

        candles = series.candles[-6:]

        highs = [c.high for c in candles]

        lows = [c.low for c in candles]

        if max(highs) - min(highs) <= max(highs) * self.TOLERANCE:

            return Signal(
                direction="SELL",
                confidence=80,
                reason="Equal Highs detected",
            )

        if max(lows) - min(lows) <= max(lows) * self.TOLERANCE:

            return Signal(
                direction="BUY",
                confidence=80,
                reason="Equal Lows detected",
            )

        return Signal(
            direction="NEUTRAL",
            confidence=0,
            reason="No Equal Levels",
        )