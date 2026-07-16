from src.analysis.technical.rsi import RSIAnalyzer
from src.domain.candle_series import CandleSeries


class RSIScorer:
    """
    Converts RSI into a normalized score (0-100).
    """

    @staticmethod
    def score(
        series: CandleSeries,
        period: int = 14,
    ) -> float:

        rsi = RSIAnalyzer.calculate(series, period)

        if rsi is None:
            return 50.0

        # بهترین ناحیه برای ورود معمولاً بین 40 تا 60 است.
        if 40 <= rsi <= 60:
            return 100.0

        if rsi < 40:
            return max(0.0, rsi / 40 * 100)

        return max(0.0, (100 - rsi) / 40 * 100)