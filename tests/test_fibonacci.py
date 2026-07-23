import math

import pytest

from src.analysis.technical.fibonacci import (
    FibonacciAnalyzer,
    FibonacciLevels,
)
from src.analysis.technical.swing import SwingPoint


def create_bullish_swings() -> tuple[SwingPoint, SwingPoint]:
    return (
        SwingPoint(
            index=2,
            price=100.0,
            kind="LOW",
        ),
        SwingPoint(
            index=8,
            price=120.0,
            kind="HIGH",
        ),
    )


def create_bearish_swings() -> tuple[SwingPoint, SwingPoint]:
    return (
        SwingPoint(
            index=3,
            price=120.0,
            kind="HIGH",
        ),
        SwingPoint(
            index=9,
            price=100.0,
            kind="LOW",
        ),
    )


def test_calculate_bullish_fibonacci_levels() -> None:
    start, end = create_bullish_swings()

    levels = FibonacciAnalyzer.calculate(start, end)

    assert isinstance(levels, FibonacciLevels)
    assert levels.direction == "BULLISH"
    assert levels.start_price == pytest.approx(100.0)
    assert levels.end_price == pytest.approx(120.0)
    assert levels.level_0 == pytest.approx(120.0)
    assert levels.level_236 == pytest.approx(115.28)
    assert levels.level_382 == pytest.approx(112.36)
    assert levels.level_500 == pytest.approx(110.0)
    assert levels.level_618 == pytest.approx(107.64)
    assert levels.level_786 == pytest.approx(104.28)
    assert levels.level_100 == pytest.approx(100.0)


def test_calculate_bearish_fibonacci_levels() -> None:
    start, end = create_bearish_swings()

    levels = FibonacciAnalyzer.calculate(start, end)

    assert levels.direction == "BEARISH"
    assert levels.start_price == pytest.approx(120.0)
    assert levels.end_price == pytest.approx(100.0)
    assert levels.level_0 == pytest.approx(100.0)
    assert levels.level_236 == pytest.approx(104.72)
    assert levels.level_382 == pytest.approx(107.64)
    assert levels.level_500 == pytest.approx(110.0)
    assert levels.level_618 == pytest.approx(112.36)
    assert levels.level_786 == pytest.approx(115.72)
    assert levels.level_100 == pytest.approx(120.0)


def test_as_dict_returns_all_supported_ratios() -> None:
    start, end = create_bullish_swings()

    values = FibonacciAnalyzer.calculate(start, end).as_dict()

    assert tuple(values.keys()) == FibonacciAnalyzer.RATIOS
    assert values[0.0] == pytest.approx(120.0)
    assert values[0.5] == pytest.approx(110.0)
    assert values[1.0] == pytest.approx(100.0)


def test_nearest_level() -> None:
    start, end = create_bullish_swings()
    levels = FibonacciAnalyzer.calculate(start, end)

    ratio, level_price = FibonacciAnalyzer.nearest_level(
        price=107.5,
        levels=levels,
    )

    assert ratio == pytest.approx(0.618)
    assert level_price == pytest.approx(107.64)


def test_rejects_reversed_swing_indexes() -> None:
    start = SwingPoint(
        index=8,
        price=100.0,
        kind="LOW",
    )
    end = SwingPoint(
        index=2,
        price=120.0,
        kind="HIGH",
    )

    with pytest.raises(
        ValueError,
        match="start swing must occur before end swing",
    ):
        FibonacciAnalyzer.calculate(start, end)


def test_rejects_equal_swing_indexes() -> None:
    start = SwingPoint(
        index=2,
        price=100.0,
        kind="LOW",
    )
    end = SwingPoint(
        index=2,
        price=120.0,
        kind="HIGH",
    )

    with pytest.raises(
        ValueError,
        match="start swing must occur before end swing",
    ):
        FibonacciAnalyzer.calculate(start, end)


def test_rejects_equal_prices() -> None:
    start = SwingPoint(
        index=2,
        price=100.0,
        kind="LOW",
    )
    end = SwingPoint(
        index=8,
        price=100.0,
        kind="HIGH",
    )

    with pytest.raises(
        ValueError,
        match="start and end prices must be different",
    ):
        FibonacciAnalyzer.calculate(start, end)


@pytest.mark.parametrize(
    ("start_kind", "end_kind"),
    [
        ("HIGH", "HIGH"),
        ("LOW", "LOW"),
    ],
)
def test_rejects_invalid_swing_pair(
    start_kind: str,
    end_kind: str,
) -> None:
    start = SwingPoint(
        index=2,
        price=100.0,
        kind=start_kind,  # type: ignore[arg-type]
    )
    end = SwingPoint(
        index=8,
        price=120.0,
        kind=end_kind,  # type: ignore[arg-type]
    )

    with pytest.raises(
        ValueError,
        match="swings must form",
    ):
        FibonacciAnalyzer.calculate(start, end)


def test_rejects_invalid_bullish_prices() -> None:
    start = SwingPoint(
        index=2,
        price=120.0,
        kind="LOW",
    )
    end = SwingPoint(
        index=8,
        price=100.0,
        kind="HIGH",
    )

    with pytest.raises(
        ValueError,
        match="bullish Fibonacci requires",
    ):
        FibonacciAnalyzer.calculate(start, end)


def test_rejects_invalid_bearish_prices() -> None:
    start = SwingPoint(
        index=2,
        price=100.0,
        kind="HIGH",
    )
    end = SwingPoint(
        index=8,
        price=120.0,
        kind="LOW",
    )

    with pytest.raises(
        ValueError,
        match="bearish Fibonacci requires",
    ):
        FibonacciAnalyzer.calculate(start, end)


@pytest.mark.parametrize(
    "invalid_price",
    [
        0.0,
        -1.0,
        math.nan,
        math.inf,
        -math.inf,
    ],
)
def test_rejects_invalid_swing_price(
    invalid_price: float,
) -> None:
    start = SwingPoint(
        index=2,
        price=invalid_price,
        kind="LOW",
    )
    end = SwingPoint(
        index=8,
        price=120.0,
        kind="HIGH",
    )

    with pytest.raises(ValueError):
        FibonacciAnalyzer.calculate(start, end)


def test_rejects_invalid_start_object() -> None:
    _, end = create_bullish_swings()

    with pytest.raises(
        TypeError,
        match="start must be a SwingPoint instance",
    ):
        FibonacciAnalyzer.calculate(
            None,  # type: ignore[arg-type]
            end,
        )


@pytest.mark.parametrize(
    "invalid_price",
    [
        0.0,
        -1.0,
        math.nan,
        math.inf,
        -math.inf,
    ],
)
def test_nearest_level_rejects_invalid_price(
    invalid_price: float,
) -> None:
    start, end = create_bullish_swings()
    levels = FibonacciAnalyzer.calculate(start, end)

    with pytest.raises(ValueError):
        FibonacciAnalyzer.nearest_level(
            invalid_price,
            levels,
        )


def test_nearest_level_rejects_invalid_levels() -> None:
    with pytest.raises(
        TypeError,
        match="levels must be a FibonacciLevels instance",
    ):
        FibonacciAnalyzer.nearest_level(
            110.0,
            None,  # type: ignore[arg-type]
        )


def test_fibonacci_levels_are_immutable() -> None:
    start, end = create_bullish_swings()
    levels = FibonacciAnalyzer.calculate(start, end)

    with pytest.raises(AttributeError):
        levels.level_618 = 99.0  # type: ignore[misc]