import math

import pytest

from src.analysis.smart_money.fair_value_gap import (
    FairValueGap,
    FairValueGapEngine,
)


@pytest.fixture
def engine() -> FairValueGapEngine:
    return FairValueGapEngine()


def test_detects_bullish_fair_value_gap(
    engine: FairValueGapEngine,
) -> None:
    result = engine.detect(
        candle1_high=118_000,
        candle1_low=117_000,
        candle2_high=118_500,
        candle2_low=117_500,
        candle3_high=119_500,
        candle3_low=118_300,
    )

    assert result == FairValueGap(
        bullish=True,
        bearish=False,
        top=118_300.0,
        bottom=118_000.0,
        valid=True,
    )


def test_detects_bearish_fair_value_gap(
    engine: FairValueGapEngine,
) -> None:
    result = engine.detect(
        candle1_high=119_000,
        candle1_low=118_000,
        candle2_high=118_500,
        candle2_low=117_500,
        candle3_high=117_700,
        candle3_low=116_800,
    )

    assert result == FairValueGap(
        bullish=False,
        bearish=True,
        top=118_000.0,
        bottom=117_700.0,
        valid=True,
    )


def test_returns_invalid_result_when_no_gap_exists(
    engine: FairValueGapEngine,
) -> None:
    result = engine.detect(
        candle1_high=118_000,
        candle1_low=117_000,
        candle2_high=118_500,
        candle2_low=117_500,
        candle3_high=118_300,
        candle3_low=117_800,
    )

    assert result == FairValueGap(
        bullish=False,
        bearish=False,
        top=None,
        bottom=None,
        valid=False,
    )


def test_equal_bullish_boundary_is_not_a_gap(
    engine: FairValueGapEngine,
) -> None:
    result = engine.detect(
        candle1_high=118_000,
        candle1_low=117_000,
        candle2_high=118_500,
        candle2_low=117_500,
        candle3_high=119_000,
        candle3_low=118_000,
    )

    assert result.valid is False
    assert result.bullish is False
    assert result.bearish is False
    assert result.top is None
    assert result.bottom is None


def test_equal_bearish_boundary_is_not_a_gap(
    engine: FairValueGapEngine,
) -> None:
    result = engine.detect(
        candle1_high=119_000,
        candle1_low=118_000,
        candle2_high=118_500,
        candle2_low=117_500,
        candle3_high=118_000,
        candle3_low=117_000,
    )

    assert result.valid is False
    assert result.bullish is False
    assert result.bearish is False
    assert result.top is None
    assert result.bottom is None


def test_bullish_gap_size(
    engine: FairValueGapEngine,
) -> None:
    result = engine.detect(
        candle1_high=118_000,
        candle1_low=117_000,
        candle2_high=118_500,
        candle2_low=117_500,
        candle3_high=119_500,
        candle3_low=118_300,
    )

    assert result.size == pytest.approx(300.0)


def test_bearish_gap_size(
    engine: FairValueGapEngine,
) -> None:
    result = engine.detect(
        candle1_high=119_000,
        candle1_low=118_000,
        candle2_high=118_500,
        candle2_low=117_500,
        candle3_high=117_700,
        candle3_low=116_800,
    )

    assert result.size == pytest.approx(300.0)


def test_invalid_gap_size_is_zero(
    engine: FairValueGapEngine,
) -> None:
    result = engine.detect(
        candle1_high=118_000,
        candle1_low=117_000,
        candle2_high=118_500,
        candle2_low=117_500,
        candle3_high=118_300,
        candle3_low=117_800,
    )

    assert result.size == 0.0


def test_bullish_gap_midpoint(
    engine: FairValueGapEngine,
) -> None:
    result = engine.detect(
        candle1_high=118_000,
        candle1_low=117_000,
        candle2_high=118_500,
        candle2_low=117_500,
        candle3_high=119_500,
        candle3_low=118_400,
    )

    assert result.midpoint == pytest.approx(118_200.0)


def test_bearish_gap_midpoint(
    engine: FairValueGapEngine,
) -> None:
    result = engine.detect(
        candle1_high=119_000,
        candle1_low=118_000,
        candle2_high=118_500,
        candle2_low=117_500,
        candle3_high=117_600,
        candle3_low=116_800,
    )

    assert result.midpoint == pytest.approx(117_800.0)


def test_invalid_gap_midpoint_is_none(
    engine: FairValueGapEngine,
) -> None:
    result = engine.detect(
        candle1_high=118_000,
        candle1_low=117_000,
        candle2_high=118_500,
        candle2_low=117_500,
        candle3_high=118_300,
        candle3_low=117_800,
    )

    assert result.midpoint is None


def test_accepts_integer_and_float_prices(
    engine: FairValueGapEngine,
) -> None:
    result = engine.detect(
        candle1_high=118_000,
        candle1_low=117_000.0,
        candle2_high=118_500.5,
        candle2_low=117_500,
        candle3_high=119_500,
        candle3_low=118_300.25,
    )

    assert result.valid is True
    assert result.bullish is True
    assert result.top == pytest.approx(118_300.25)
    assert result.bottom == pytest.approx(118_000.0)


@pytest.mark.parametrize(
    "invalid_price",
    [
        0,
        -1,
        -100.5,
    ],
)
def test_rejects_non_positive_prices(
    engine: FairValueGapEngine,
    invalid_price: float,
) -> None:
    with pytest.raises(
        ValueError,
        match="candle1_high must be greater than zero",
    ):
        engine.detect(
            candle1_high=invalid_price,
            candle1_low=117_000,
            candle2_high=118_500,
            candle2_low=117_500,
            candle3_high=119_500,
            candle3_low=118_300,
        )


@pytest.mark.parametrize(
    "invalid_price",
    [
        math.nan,
        math.inf,
        -math.inf,
    ],
)
def test_rejects_non_finite_prices(
    engine: FairValueGapEngine,
    invalid_price: float,
) -> None:
    with pytest.raises(
        ValueError,
        match="candle2_low must be finite",
    ):
        engine.detect(
            candle1_high=118_000,
            candle1_low=117_000,
            candle2_high=118_500,
            candle2_low=invalid_price,
            candle3_high=119_500,
            candle3_low=118_300,
        )


@pytest.mark.parametrize(
    "invalid_price",
    [
        "118000",
        None,
        True,
        False,
    ],
)
def test_rejects_non_numeric_prices(
    engine: FairValueGapEngine,
    invalid_price: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="candle3_high must be a number",
    ):
        engine.detect(
            candle1_high=118_000,
            candle1_low=117_000,
            candle2_high=118_500,
            candle2_low=117_500,
            candle3_high=invalid_price,  # type: ignore[arg-type]
            candle3_low=118_300,
        )


def test_rejects_invalid_first_candle(
    engine: FairValueGapEngine,
) -> None:
    with pytest.raises(
        ValueError,
        match=(
            "candle1_high must be greater than or equal "
            "to candle1_low"
        ),
    ):
        engine.detect(
            candle1_high=117_000,
            candle1_low=118_000,
            candle2_high=118_500,
            candle2_low=117_500,
            candle3_high=119_500,
            candle3_low=118_300,
        )


def test_rejects_invalid_second_candle(
    engine: FairValueGapEngine,
) -> None:
    with pytest.raises(
        ValueError,
        match=(
            "candle2_high must be greater than or equal "
            "to candle2_low"
        ),
    ):
        engine.detect(
            candle1_high=118_000,
            candle1_low=117_000,
            candle2_high=117_000,
            candle2_low=118_000,
            candle3_high=119_500,
            candle3_low=118_300,
        )


def test_rejects_invalid_third_candle(
    engine: FairValueGapEngine,
) -> None:
    with pytest.raises(
        ValueError,
        match=(
            "candle3_high must be greater than or equal "
            "to candle3_low"
        ),
    ):
        engine.detect(
            candle1_high=118_000,
            candle1_low=117_000,
            candle2_high=118_500,
            candle2_low=117_500,
            candle3_high=118_000,
            candle3_low=119_000,
        )


def test_accepts_zero_range_candles(
    engine: FairValueGapEngine,
) -> None:
    result = engine.detect(
        candle1_high=118_000,
        candle1_low=118_000,
        candle2_high=118_500,
        candle2_low=118_500,
        candle3_high=119_000,
        candle3_low=119_000,
    )

    assert result.valid is True
    assert result.bullish is True
    assert result.top == pytest.approx(119_000.0)
    assert result.bottom == pytest.approx(118_000.0)


def test_result_is_immutable() -> None:
    result = FairValueGap(
        bullish=True,
        bearish=False,
        top=118_300.0,
        bottom=118_000.0,
        valid=True,
    )

    with pytest.raises(AttributeError):
        result.top = 120_000.0  # type: ignore[misc]


def test_rejects_both_directions() -> None:
    with pytest.raises(
        ValueError,
        match="cannot be both bullish and bearish",
    ):
        FairValueGap(
            bullish=True,
            bearish=True,
            top=118_300.0,
            bottom=118_000.0,
            valid=True,
        )


def test_rejects_valid_gap_without_direction() -> None:
    with pytest.raises(
        ValueError,
        match="must have a direction",
    ):
        FairValueGap(
            bullish=False,
            bearish=False,
            top=118_300.0,
            bottom=118_000.0,
            valid=True,
        )


def test_rejects_valid_gap_without_boundaries() -> None:
    with pytest.raises(
        ValueError,
        match="must have top and bottom",
    ):
        FairValueGap(
            bullish=True,
            bearish=False,
            top=None,
            bottom=None,
            valid=True,
        )


def test_rejects_invalid_gap_with_boundaries() -> None:
    with pytest.raises(
        ValueError,
        match="cannot have boundaries",
    ):
        FairValueGap(
            bullish=False,
            bearish=False,
            top=118_300.0,
            bottom=118_000.0,
            valid=False,
        )