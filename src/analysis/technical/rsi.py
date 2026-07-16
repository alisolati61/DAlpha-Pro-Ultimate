from __future__ import annotations

from src.domain.candle_series import CandleSeries


class RSIAnalyzer:
    """
    Production RSI (Wilder RSI)
    """

    @staticmethod
    def calculate(
        series: CandleSeries,
        period: int = 14,
    ) -> float | None:

        closes = [c.close for c in series.candles]

        if len(closes) < period + 1:
            return None

        gains = []
        losses = []

        for i in range(1, len(closes)):
            change = closes[i] - closes[i - 1]

            gains.append(max(change, 0))
            losses.append(max(-change, 0))

        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period

        for i in range(period, len(gains)):
            avg_gain = ((avg_gain * (period - 1)) + gains[i]) / period
            avg_loss = ((avg_loss * (period - 1)) + losses[i]) / period

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss

        rsi = 100 - (100 / (1 + rs))

        return round(rsi, 2)

    @staticmethod
    def is_overbought(
        series: CandleSeries,
        period: int = 14,
        level: float = 70,
    ) -> bool:

        value = RSIAnalyzer.calculate(series, period)

        return value is not None and value >= level

    @staticmethod
    def is_oversold(
        series: CandleSeries,
        period: int = 14,
        level: float = 30,
    ) -> bool:

        value = RSIAnalyzer.calculate(series, period)

        return value is not None and value <= level