from dataclasses import dataclass

from src.domain.candle_series import CandleSeries


@dataclass(slots=True)
class SwingPoint:
    index: int
    price: float
    kind: str  # HIGH | LOW


class SwingAnalyzer:
    """
    Detect Swing Highs and Swing Lows.

    Foundation for:
    - BOS
    - CHOCH
    - Order Block
    - Liquidity Sweep
    """

    @staticmethod
    def highs(
        series: CandleSeries,
        lookback: int = 2,
    ) -> list[SwingPoint]:

        candles = series.candles
        swings = []

        if len(candles) < (lookback * 2 + 1):
            return swings

        for i in range(lookback, len(candles) - lookback):

            current = candles[i].high

            left = [
                candles[j].high
                for j in range(i - lookback, i)
            ]

            right = [
                candles[j].high
                for j in range(i + 1, i + lookback + 1)
            ]

            if current >= max(left) and current >= max(right):

                swings.append(
                    SwingPoint(
                        index=i,
                        price=current,
                        kind="HIGH",
                    )
                )

        return swings

    @staticmethod
    def lows(
        series: CandleSeries,
        lookback: int = 2,
    ) -> list[SwingPoint]:

        candles = series.candles
        swings = []

        if len(candles) < (lookback * 2 + 1):
            return swings

        for i in range(lookback, len(candles) - lookback):

            current = candles[i].low

            left = [
                candles[j].low
                for j in range(i - lookback, i)
            ]

            right = [
                candles[j].low
                for j in range(i + 1, i + lookback + 1)
            ]

            if current <= min(left) and current <= min(right):

                swings.append(
                    SwingPoint(
                        index=i,
                        price=current,
                        kind="LOW",
                    )
                )

        return swings

    @staticmethod
    def latest_high(
        series: CandleSeries,
        lookback: int = 2,
    ) -> SwingPoint | None:

        highs = SwingAnalyzer.highs(series, lookback)

        return highs[-1] if highs else None

    @staticmethod
    def latest_low(
        series: CandleSeries,
        lookback: int = 2,
    ) -> SwingPoint | None:

        lows = SwingAnalyzer.lows(series, lookback)

        return lows[-1] if lows else None