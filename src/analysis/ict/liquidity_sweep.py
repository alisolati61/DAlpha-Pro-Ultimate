from __future__ import annotations

from src.analysis.ict.ict_engine import ICTModule
from src.analysis.signal_engine import Signal
from src.domain.candle_series import CandleSeries


class LiquiditySweepAnalyzer(ICTModule):
    """
    ICT Liquidity Sweep detector.
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

        # Buy-side liquidity sweep
        if (
            current.high > previous.high
            and current.close < previous.high
        ):

            return Signal(
                direction="SELL",
                confidence=92,
                reason="Buy-side Liquidity Sweep",
            )

        # Sell-side liquidity sweep
        if (
            current.low < previous.low
            and current.close > previous.low
        ):

            return Signal(
                direction="BUY",
                confidence=92,
                reason="Sell-side Liquidity Sweep",
            )

        return Signal(
            direction="NEUTRAL",
            confidence=0,
            reason="No Liquidity Sweep",
        )