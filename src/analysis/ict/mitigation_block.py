from __future__ import annotations

from src.analysis.ict.ict_engine import ICTModule
from src.analysis.signal_engine import Signal
from src.domain.candle_series import CandleSeries


class MitigationBlockAnalyzer(ICTModule):
    """
    ICT Mitigation Block detector.
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
            current.low <= previous.low
            and current.close > previous.close
        ):

            return Signal(
                direction="BUY",
                confidence=87,
                reason="Bullish Mitigation Block",
            )

        if (
            current.high >= previous.high
            and current.close < previous.close
        ):

            return Signal(
                direction="SELL",
                confidence=87,
                reason="Bearish Mitigation Block",
            )

        return Signal(
            direction="NEUTRAL",
            confidence=0,
            reason="No Mitigation Block",
        )