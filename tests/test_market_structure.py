"""Tests for smart-money market-structure analysis."""

from dataclasses import FrozenInstanceError
from math import inf, nan

import pytest

from src.analysis.smart_money.market_structure import (
    MarketStructure,
    MarketStructureEngine,
    SwingPoint,
    Trend,
)


def test_trend_values_preserve_public_contract() -> None:
    assert Trend.BULLISH.value == "BULLISH"
    assert Trend.BEARISH.value == "BEARISH"
    assert Trend.SIDEWAYS.value == "SIDEWAYS"


def test_empty_series_returns_sideways_structure() -> None:
    result = MarketStructureEngine().analyze(
        [],
        [],
    )

    assert result.trend is Trend.SIDEWAYS
    assert result.higher_highs == ()
    assert result.higher_lows == ()
    assert result.lower_highs == ()
    assert result.lower_lows == ()
    assert result.structural_point_count == 0


def test_single_range_returns_sideways_structure() -> None:
    result = MarketStructureEngine().analyze(
        [110.0],
        [100.0],
    )

    assert result.sideways is True
    assert result.bullish is False
    assert result.bearish is False
    assert result.structural_point_count == 0


def test_detects_bullish_latest_structure() -> None:
    result = MarketStructureEngine().analyze(
        [110.0, 112.0],
        [100.0, 102.0],
    )

    assert result.trend is Trend.BULLISH
    assert result.bullish is True

    assert result.higher_highs == (
        SwingPoint(1, 112.0),
    )
    assert result.higher_lows == (
        SwingPoint(1, 102.0),
    )

    assert result.lower_highs == ()
    assert result.lower_lows == ()


def test_detects_bearish_latest_structure() -> None:
    result = MarketStructureEngine().analyze(
        [110.0, 108.0],
        [100.0, 98.0],
    )

    assert result.trend is Trend.BEARISH
    assert result.bearish is True

    assert result.lower_highs == (
        SwingPoint(1, 108.0),
    )
    assert result.lower_lows == (
        SwingPoint(1, 98.0),
    )


@pytest.mark.parametrize(
    ("highs", "lows"),
    [
        (
            [110.0, 112.0],
            [100.0, 99.0],
        ),
        (
            [110.0, 108.0],
            [100.0, 101.0],
        ),
        (
            [110.0, 110.0],
            [100.0, 101.0],
        ),
        (
            [110.0, 111.0],
            [100.0, 100.0],
        ),
        (
            [110.0, 110.0],
            [100.0, 100.0],
        ),
    ],
)
def test_mixed_or_equal_latest_structure_is_sideways(
    highs: list[float],
    lows: list[float],
) -> None:
    result = MarketStructureEngine().analyze(
        highs,
        lows,
    )

    assert result.trend is Trend.SIDEWAYS
    assert result.sideways is True


def test_classifies_every_observation() -> None:
    result = MarketStructureEngine().analyze(
        [
            100.0,
            105.0,
            103.0,
            103.0,
            108.0,
        ],
        [
            90.0,
            92.0,
            91.0,
            93.0,
            93.0,
        ],
    )

    assert result.higher_highs == (
        SwingPoint(1, 105.0),
        SwingPoint(4, 108.0),
    )

    assert result.lower_highs == (
        SwingPoint(2, 103.0),
    )

    assert result.higher_lows == (
        SwingPoint(1, 92.0),
        SwingPoint(3, 93.0),
    )

    assert result.lower_lows == (
        SwingPoint(2, 91.0),
    )

    assert result.structural_point_count == 6
    assert result.trend is Trend.SIDEWAYS


def test_equal_levels_are_not_classified() -> None:
    result = MarketStructureEngine().analyze(
        [110.0, 110.0, 111.0],
        [100.0, 100.0, 101.0],
    )

    assert result.higher_highs == (
        SwingPoint(2, 111.0),
    )

    assert result.higher_lows == (
        SwingPoint(2, 101.0),
    )

    assert result.structural_point_count == 2


def test_latest_properties_return_last_classified_points() -> None:
    result = MarketStructureEngine().analyze(
        [
            100.0,
            102.0,
            101.0,
            105.0,
        ],
        [
            90.0,
            92.0,
            91.0,
            94.0,
        ],
    )

    assert result.latest_higher_high == SwingPoint(
        3,
        105.0,
    )
    assert result.latest_higher_low == SwingPoint(
        3,
        94.0,
    )
    assert result.latest_lower_high == SwingPoint(
        2,
        101.0,
    )
    assert result.latest_lower_low == SwingPoint(
        2,
        91.0,
    )


def test_latest_properties_return_none_when_category_is_empty() -> None:
    result = MarketStructureEngine().analyze(
        [100.0, 101.0],
        [90.0, 91.0],
    )

    assert result.latest_lower_high is None
    assert result.latest_lower_low is None


def test_accepts_generators() -> None:
    result = MarketStructureEngine().analyze(
        (
            value
            for value in [110, 112]
        ),
        (
            value
            for value in [100, 102]
        ),
    )

    assert result.trend is Trend.BULLISH
    assert result.higher_highs[0].price == 112.0

    assert isinstance(
        result.higher_highs[0].price,
        float,
    )


def test_rejects_mismatched_lengths() -> None:
    with pytest.raises(
        ValueError,
        match="highs and lows must have the same length",
    ):
        MarketStructureEngine().analyze(
            [110.0, 111.0],
            [100.0],
        )


@pytest.mark.parametrize(
    ("name", "values"),
    [
        (
            "highs",
            110.0,
        ),
        (
            "lows",
            None,
        ),
        (
            "highs",
            "110,111",
        ),
        (
            "lows",
            b"100,101",
        ),
    ],
)
def test_rejects_non_iterable_or_string_series(
    name: str,
    values: object,
) -> None:
    highs: object = [
        110.0,
        111.0,
    ]
    lows: object = [
        100.0,
        101.0,
    ]

    if name == "highs":
        highs = values
    else:
        lows = values

    with pytest.raises(
        TypeError,
        match=(
            rf"{name} must be an iterable "
            rf"of real numbers"
        ),
    ):
        MarketStructureEngine().analyze(
            highs,  # type: ignore[arg-type]
            lows,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    ("series", "index", "value"),
    [
        (
            "highs",
            0,
            "110",
        ),
        (
            "highs",
            1,
            True,
        ),
        (
            "lows",
            0,
            None,
        ),
        (
            "lows",
            1,
            object(),
        ),
    ],
)
def test_rejects_non_numeric_prices(
    series: str,
    index: int,
    value: object,
) -> None:
    highs: list[object] = [
        110.0,
        111.0,
    ]
    lows: list[object] = [
        100.0,
        101.0,
    ]

    target = (
        highs
        if series == "highs"
        else lows
    )

    target[index] = value

    with pytest.raises(
        TypeError,
        match=(
            rf"{series}\[{index}\] "
            rf"must be a real number"
        ),
    ):
        MarketStructureEngine().analyze(
            highs,  # type: ignore[arg-type]
            lows,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    ("series", "index", "value"),
    [
        (
            "highs",
            0,
            nan,
        ),
        (
            "highs",
            1,
            inf,
        ),
        (
            "lows",
            0,
            -inf,
        ),
        (
            "lows",
            1,
            nan,
        ),
    ],
)
def test_rejects_non_finite_prices(
    series: str,
    index: int,
    value: float,
) -> None:
    highs = [
        110.0,
        111.0,
    ]
    lows = [
        100.0,
        101.0,
    ]

    target = (
        highs
        if series == "highs"
        else lows
    )

    target[index] = value

    with pytest.raises(
        ValueError,
        match=(
            rf"{series}\[{index}\] "
            rf"must be finite"
        ),
    ):
        MarketStructureEngine().analyze(
            highs,
            lows,
        )


@pytest.mark.parametrize(
    ("series", "index", "value"),
    [
        (
            "highs",
            0,
            0.0,
        ),
        (
            "highs",
            1,
            -1.0,
        ),
        (
            "lows",
            0,
            0.0,
        ),
        (
            "lows",
            1,
            -0.01,
        ),
    ],
)
def test_rejects_non_positive_prices(
    series: str,
    index: int,
    value: float,
) -> None:
    highs = [
        110.0,
        111.0,
    ]
    lows = [
        100.0,
        101.0,
    ]

    target = (
        highs
        if series == "highs"
        else lows
    )

    target[index] = value

    with pytest.raises(
        ValueError,
        match=(
            rf"{series}\[{index}\] "
            rf"must be greater than zero"
        ),
    ):
        MarketStructureEngine().analyze(
            highs,
            lows,
        )


def test_rejects_high_below_low_at_same_index() -> None:
    with pytest.raises(
        ValueError,
        match=(
            r"highs\[1\] must be greater than or equal "
            r"to lows\[1\]"
        ),
    ):
        MarketStructureEngine().analyze(
            [110.0, 99.0],
            [100.0, 101.0],
        )


def test_accepts_zero_range_observation() -> None:
    result = MarketStructureEngine().analyze(
        [100.0, 101.0],
        [100.0, 101.0],
    )

    assert result.trend is Trend.BULLISH


@pytest.mark.parametrize(
    "index",
    [
        True,
        1.5,
        "1",
        None,
    ],
)
def test_swing_point_rejects_non_integer_index(
    index: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="index must be an integer",
    ):
        SwingPoint(
            index=index,  # type: ignore[arg-type]
            price=100.0,
        )


def test_swing_point_rejects_negative_index() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "index must be greater than "
            "or equal to zero"
        ),
    ):
        SwingPoint(
            index=-1,
            price=100.0,
        )


@pytest.mark.parametrize(
    ("price", "error", "message"),
    [
        (
            "100",
            TypeError,
            "price must be a real number",
        ),
        (
            True,
            TypeError,
            "price must be a real number",
        ),
        (
            nan,
            ValueError,
            "price must be finite",
        ),
        (
            inf,
            ValueError,
            "price must be finite",
        ),
        (
            0.0,
            ValueError,
            "price must be greater than zero",
        ),
        (
            -1.0,
            ValueError,
            "price must be greater than zero",
        ),
    ],
)
def test_swing_point_validates_price(
    price: object,
    error: type[Exception],
    message: str,
) -> None:
    with pytest.raises(
        error,
        match=message,
    ):
        SwingPoint(
            index=0,
            price=price,  # type: ignore[arg-type]
        )


def test_swing_point_is_immutable() -> None:
    point = SwingPoint(
        index=1,
        price=100.0,
    )

    with pytest.raises(FrozenInstanceError):
        point.price = 101.0  # type: ignore[misc]


def test_market_structure_accepts_lists_and_normalizes_to_tuples() -> None:
    result = MarketStructure(
        trend=Trend.BULLISH,
        higher_highs=[
            SwingPoint(1, 110.0),
        ],  # type: ignore[arg-type]
        higher_lows=[
            SwingPoint(1, 100.0),
        ],  # type: ignore[arg-type]
        lower_highs=[],  # type: ignore[arg-type]
        lower_lows=[],  # type: ignore[arg-type]
    )

    assert result.higher_highs == (
        SwingPoint(1, 110.0),
    )

    assert isinstance(
        result.higher_highs,
        tuple,
    )


def test_market_structure_rejects_invalid_trend() -> None:
    with pytest.raises(
        TypeError,
        match="trend must be a Trend instance",
    ):
        MarketStructure(
            trend="BULLISH",  # type: ignore[arg-type]
            higher_highs=(),
            higher_lows=(),
            lower_highs=(),
            lower_lows=(),
        )


@pytest.mark.parametrize(
    "field",
    [
        "higher_highs",
        "higher_lows",
        "lower_highs",
        "lower_lows",
    ],
)
def test_market_structure_rejects_non_swing_points(
    field: str,
) -> None:
    arguments: dict[str, object] = {
        "trend": Trend.SIDEWAYS,
        "higher_highs": (),
        "higher_lows": (),
        "lower_highs": (),
        "lower_lows": (),
    }

    arguments[field] = [
        object(),
    ]

    with pytest.raises(
        TypeError,
        match=(
            rf"{field} must contain only "
            rf"SwingPoint instances"
        ),
    ):
        MarketStructure(
            **arguments,  # type: ignore[arg-type]
        )


def test_market_structure_rejects_duplicate_indexes() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "higher_highs cannot contain "
            "duplicate indexes"
        ),
    ):
        MarketStructure(
            trend=Trend.BULLISH,
            higher_highs=(
                SwingPoint(1, 110.0),
                SwingPoint(1, 111.0),
            ),
            higher_lows=(),
            lower_highs=(),
            lower_lows=(),
        )


def test_market_structure_rejects_unordered_indexes() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "higher_highs must be "
            "ordered by index"
        ),
    ):
        MarketStructure(
            trend=Trend.BULLISH,
            higher_highs=(
                SwingPoint(2, 111.0),
                SwingPoint(1, 110.0),
            ),
            higher_lows=(),
            lower_highs=(),
            lower_lows=(),
        )


@pytest.mark.parametrize(
    (
        "first_field",
        "second_field",
        "message",
    ),
    [
        (
            "higher_highs",
            "lower_highs",
            (
                "higher_highs and lower_highs "
                "cannot share indexes"
            ),
        ),
        (
            "higher_lows",
            "lower_lows",
            (
                "higher_lows and lower_lows "
                "cannot share indexes"
            ),
        ),
    ],
)
def test_market_structure_rejects_conflicting_indexes(
    first_field: str,
    second_field: str,
    message: str,
) -> None:
    arguments: dict[str, object] = {
        "trend": Trend.SIDEWAYS,
        "higher_highs": (),
        "higher_lows": (),
        "lower_highs": (),
        "lower_lows": (),
    }

    arguments[first_field] = (
        SwingPoint(1, 110.0),
    )
    arguments[second_field] = (
        SwingPoint(1, 100.0),
    )

    with pytest.raises(
        ValueError,
        match=message,
    ):
        MarketStructure(
            **arguments,  # type: ignore[arg-type]
        )


def test_market_structure_is_immutable() -> None:
    result = MarketStructureEngine().analyze(
        [110.0, 112.0],
        [100.0, 102.0],
    )

    with pytest.raises(FrozenInstanceError):
        result.trend = Trend.BEARISH  # type: ignore[misc]