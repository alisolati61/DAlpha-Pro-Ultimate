from __future__ import annotations

from dataclasses import dataclass

from src.analysis.signal_engine import Signal
from src.analysis.ict.ict_engine import ICTModule
from src.domain.candle_series import CandleSeries


@dataclass(slots=True)
class FairValueGap:

    start: float

    end: float

    bullish: bool


class FairValueGapAnalyzer(ICTModule):
    """
    Detect ICT Fair Value Gaps (3-candle imbalance).
    """

    def analyze(
        self,
        series: CandleSeries,
    ) -> Signal:

        if len(series.candles) < 3:

            return Signal(
                direction="NEUTRAL",
                confidence=0,
                reason="Not enough candles",
            )

        candles = series.candles

        c1 = candles[-3]

        c2 = candles[-2]

        c3 = candles[-1]

        if c1.high < c3.low:

            return Signal(
                direction="BUY",
                confidence=85,
                reason="Bullish Fair Value Gap",
            )

        if c1.low > c3.high:

            return Signal(
                direction="SELL",
                confidence=85,
                reason="Bearish Fair Value Gap",
            )

        return Signal(
            direction="NEUTRAL",
            confidence=0,
            reason="No Fair Value Gap",
        )