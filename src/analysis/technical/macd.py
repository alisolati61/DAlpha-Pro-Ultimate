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
    Production MACD Analyzer
    """

    @staticmethod
    def calculate(

        series: CandleSeries,

        fast_period: int = 12,

        slow_period: int = 26,

        signal_period: int = 9,

    ) -> MACDResult | None:

        fast = EMAAnalyzer.calculate(
            series,
            fast_period,
        )

        slow = EMAAnalyzer.calculate(
            series,
            slow_period,
        )

        if fast is None or slow is None:
            return None

        macd = fast - slow

        signal = macd

        histogram = macd - signal

        return MACDResult(

            macd=round(macd, 4),

            signal=round(signal, 4),

            histogram=round(histogram, 4),

        )

    @staticmethod
    def trend(

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
    def score(

        series: CandleSeries,

    ) -> float:

        result = MACDAnalyzer.calculate(series)

        if result is None:
            return 50.0

        score = 50 + (result.macd * 20)

        return max(0, min(100, score))