from src.domain.candle_series import CandleSeries


class EMAAnalyzer:
    """
    Exponential Moving Average (EMA) analyzer.
    """

    @staticmethod
    def calculate(
        series: CandleSeries,
        period: int = 20,
    ) -> float | None:

        if len(series.candles) < period:
            return None

        closes = [c.close for c in series.candles]

        multiplier = 2 / (period + 1)

        ema = sum(closes[:period]) / period

        for price in closes[period:]:
            ema = (price - ema) * multiplier + ema

        return ema

    @staticmethod
    def is_above_ema(
        series: CandleSeries,
        period: int = 20,
    ) -> bool:

        ema = EMAAnalyzer.calculate(series, period)

        if ema is None:
            return False

        return series.last().close > ema