from __future__ import annotations

from dataclasses import dataclass

from src.analysis.technical.ema import EMAAnalyzer
from src.domain.candle_series import CandleSeries


@dataclass(slots=True)
class MACDResult:
    macd: float
    signal: float
    histogram: float


class MACDAnalyzer:
    """
    MACD analyzer.

    Provides:
    - calculate(): numerical MACD result
    - signal(): bullish, bearish, or neutral signal
    - trend(): backward-compatible alias for signal()
    - score(): normalized score from 0 to 100
    """

    @staticmethod
    def calculate(
        series: CandleSeries,
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9,
    ) -> MACDResult | None:
        if fast_period <= 0:
            raise ValueError("fast_period must be greater than zero.")

        if slow_period <= 0:
            raise ValueError("slow_period must be greater than zero.")

        if signal_period <= 0:
            raise ValueError("signal_period must be greater than zero.")

        if fast_period >= slow_period:
            raise ValueError(
                "fast_period must be smaller than slow_period."
            )

        fast_ema = EMAAnalyzer.calculate(
            series,
            fast_period,
        )

        slow_ema = EMAAnalyzer.calculate(
            series,
            slow_period,
        )

        if fast_ema is None or slow_ema is None:
            return None

        macd_value = fast_ema - slow_ema

        # The current EMA interface returns only the latest EMA value,
        # so a full EMA of the MACD history cannot yet be calculated.
        # Keep the existing neutral signal-line behavior until the
        # analyzer supports a complete MACD series.
        signal_value = macd_value
        histogram = macd_value - signal_value

        return MACDResult(
            macd=round(macd_value, 4),
            signal=round(signal_value, 4),
            histogram=round(histogram, 4),
        )

    @staticmethod
    def signal(
        series: CandleSeries,
    ) -> str:
        result = MACDAnalyzer.calculate(series)

        if result is None:
            return "NEUTRAL"

        if result.macd > result.signal:
            return "BULLISH"

        if result.macd < result.signal:
            return "BEARISH"

        return "NEUTRAL"

    @staticmethod
    def trend(
        series: CandleSeries,
    ) -> str:
        """
        Backward-compatible alias for signal().
        """
        return MACDAnalyzer.signal(series)

    @staticmethod
    def score(
        series: CandleSeries,
    ) -> float:
        result = MACDAnalyzer.calculate(series)

        if result is None:
            return 50.0

        score = 50.0 + (result.macd * 20.0)

        return max(
            0.0,
            min(100.0, score),
        )