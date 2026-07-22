from __future__ import annotations

from src.domain.candle_series import CandleSeries


class ATRAnalyzer:
    """
    Average True Range (ATR) analyzer.

    ATR is calculated as the simple average of the latest True Range values.
    """

    @staticmethod
    def calculate(
        series: CandleSeries,
        period: int = 14,
    ) -> float | None:
        if not isinstance(period, int) or isinstance(period, bool):
            raise TypeError("period must be an integer")

        if period <= 0:
            raise ValueError("period must be greater than zero")

        candles = series.candles

        # One previous candle is required for each True Range value.
        if len(candles) < period + 1:
            return None

        true_ranges: list[float] = []

        for index in range(1, len(candles)):
            current = candles[index]
            previous = candles[index - 1]

            true_range = max(
                current.high - current.low,
                abs(current.high - previous.close),
                abs(current.low - previous.close),
            )
            true_ranges.append(true_range)

        atr = sum(true_ranges[-period:]) / period
        return round(atr, 4)

    @staticmethod
    def volatility_score(
        series: CandleSeries,
        period: int = 14,
    ) -> float:
        atr = ATRAnalyzer.calculate(series, period)

        if atr is None:
            return 50.0

        last_close = series.last().close

        if last_close <= 0:
            return 0.0

        volatility_percentage = (atr / last_close) * 100.0

        # Lower relative volatility receives a higher stability score.
        score = 100.0 - volatility_percentage * 20.0
        score = max(0.0, min(score, 100.0))

        return round(score, 2)