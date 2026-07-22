from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from src.domain.candle_series import CandleSeries


SwingKind = Literal["HIGH", "LOW"]


@dataclass(frozen=True, slots=True)
class SwingPoint:
    index: int
    price: float
    kind: SwingKind


class SwingAnalyzer:
    """
    Detect swing highs and swing lows.

    A candle is considered a swing point when its high or low is equal
    to or more extreme than all candles on both sides within lookback.

    Foundation for:
    - BOS
    - CHOCH
    - Order Block
    - Liquidity Sweep
    """

    @staticmethod
    def _validate_inputs(
        series: CandleSeries,
        lookback: int,
    ) -> None:
        if not isinstance(series, CandleSeries):
            raise TypeError("series must be a CandleSeries instance")

        if isinstance(lookback, bool) or not isinstance(lookback, int):
            raise TypeError("lookback must be an integer")

        if lookback <= 0:
            raise ValueError("lookback must be greater than zero")

    @classmethod
    def highs(
        cls,
        series: CandleSeries,
        lookback: int = 2,
    ) -> list[SwingPoint]:
        cls._validate_inputs(series, lookback)

        candles = series.candles
        required_candles = lookback * 2 + 1

        if len(candles) < required_candles:
            return []

        swings: list[SwingPoint] = []

        for index in range(lookback, len(candles) - lookback):
            current_high = candles[index].high

            left_highs = [
                candles[position].high
                for position in range(index - lookback, index)
            ]
            right_highs = [
                candles[position].high
                for position in range(
                    index + 1,
                    index + lookback + 1,
                )
            ]

            if (
                current_high >= max(left_highs)
                and current_high >= max(right_highs)
            ):
                swings.append(
                    SwingPoint(
                        index=index,
                        price=current_high,
                        kind="HIGH",
                    )
                )

        return swings

    @classmethod
    def lows(
        cls,
        series: CandleSeries,
        lookback: int = 2,
    ) -> list[SwingPoint]:
        cls._validate_inputs(series, lookback)

        candles = series.candles
        required_candles = lookback * 2 + 1

        if len(candles) < required_candles:
            return []

        swings: list[SwingPoint] = []

        for index in range(lookback, len(candles) - lookback):
            current_low = candles[index].low

            left_lows = [
                candles[position].low
                for position in range(index - lookback, index)
            ]
            right_lows = [
                candles[position].low
                for position in range(
                    index + 1,
                    index + lookback + 1,
                )
            ]

            if (
                current_low <= min(left_lows)
                and current_low <= min(right_lows)
            ):
                swings.append(
                    SwingPoint(
                        index=index,
                        price=current_low,
                        kind="LOW",
                    )
                )

        return swings

    @classmethod
    def latest_high(
        cls,
        series: CandleSeries,
        lookback: int = 2,
    ) -> SwingPoint | None:
        swing_highs = cls.highs(series, lookback)
        return swing_highs[-1] if swing_highs else None

    @classmethod
    def latest_low(
        cls,
        series: CandleSeries,
        lookback: int = 2,
    ) -> SwingPoint | None:
        swing_lows = cls.lows(series, lookback)
        return swing_lows[-1] if swing_lows else None