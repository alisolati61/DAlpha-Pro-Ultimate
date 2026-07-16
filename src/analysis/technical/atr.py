from src.domain.candle_series import CandleSeries


class ATRAnalyzer:
    """
    Average True Range (ATR) analyzer.
    Measures market volatility.
    """

    @staticmethod
    def calculate(
        series: CandleSeries,
        period: int = 14,
    ) -> float | None:

        candles = series.candles

        if len(candles) < period + 1:
            return None

        true_ranges = []

        for i in range(1, len(candles)):

            current = candles[i]
            previous = candles[i - 1]

            tr = max(
                current.high - current.low,
                abs(current.high - previous.close),
                abs(current.low - previous.close),
            )

            true_ranges.append(tr)

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

        if last_close == 0:
            return 0.0

        volatility = (atr / last_close) * 100

        # هرچه نوسان کمتر باشد امتیاز بیشتر است
        score = max(0.0, 100.0 - volatility * 20)

        return round(min(score, 100.0), 2)