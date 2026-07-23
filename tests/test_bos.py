import math

import pytest

from src.analysis.smart_money.bos import (
    BOSEngine,
    BOSResult,
)


@pytest.fixture
def engine() -> BOSEngine:
    return BOSEngine()


def test_detects_bullish_bos(
    engine: BOSEngine,
) -> None:
    result = engine.detect(
        previous_high=118_000,
        previous_low=116_000,
        current_high=118_600,
        current_low=116_500,
    )

    assert result == BOSResult(
        bullish_bos=True,
        bearish_bos=False,
        breakout_price=118_600.0,
    )


def test_detects_bearish_bos(
    engine: BOSEngine,
) -> None:
    result = engine.detect(
        previous_high=118_000,
        previous_low=116_000,
        current_high=117_500,
        current_low=115_500,
    )

    assert result == BOSResult(
        bullish_bos=False,
        bearish_bos=True,
        breakout_price=115_500.0,
    )


def test_returns_no_bos_when_range_is_not_broken(
    engine: BOSEngine,
) -> None:
    result = engine.detect(
        previous_high=118_000,
        previous_low=116_000,
        current_high=117_900,
        current_low=116_100,
    )

    assert result == BOSResult(
        bullish_bos=False,
        bearish_bos=False,
        breakout_price=None,
    )


def test_equal_high_is_not_bullish_bos(
    engine: BOSEngine,
) -> None:
    result = engine.detect(
        previous_high=118_000,
        previous_low=116_000,
        current_high=118_000,
        current_low=116_500,
    )

    assert result.bullish_bos is False
    assert result.bearish_bos is False
    assert result.breakout_price is None


def test_equal_low_is_not_bearish_bos(
    engine: BOSEngine,
) -> None:
    result = engine.detect(
        previous_high=118_000,
        previous_low=116_000,
        current_high=117_500,
        current_low=116_000,
    )

    assert result.bullish_bos is False
    assert result.bearish_bos is False
    assert result.breakout_price is None


def test_outside_bar_is_directionally_ambiguous(
    engine: BOSEngine,
) -> None:
    result = engine.detect(
        previous_high=118_000,
        previous_low=116_000,
        current_high=118_500,
        current_low=115_500,
    )

    assert result.bullish_bos is True
    assert result.bearish_bos is True
    assert result.breakout_price is None


def test_accepts_integer_and_float_prices(
    engine: BOSEngine,
) -> None:
    result = engine.detect(
        previous_high=118_000,
        previous_low=116_000.0,
        current_high=118_600.5,
        current_low=116_500,
    )

    assert result.bullish_bos is True
    assert result.bearish_bos is False
    assert result.breakout_price == pytest.approx(118_600.5)


@pytest.mark.parametrize(
    "invalid_value",
    [
        0,
        -1,
        -100.5,
    ],
)
def test_rejects_non_positive_prices(
    engine: BOSEngine,
    invalid_value: float,
) -> None:
    with pytest.raises(
        ValueError,
        match="previous_high must be greater than zero",
    ):
        engine.detect(
            previous_high=invalid_value,
            previous_low=116_000,
            current_high=118_600,
            current_low=116_500,
        )


@pytest.mark.parametrize(
    "invalid_value",
    [
        math.nan,
        math.inf,
        -math.inf,
    ],
)
def test_rejects_non_finite_prices(
    engine: BOSEngine,
    invalid_value: float,
) -> None:
    with pytest.raises(
        ValueError,
        match="current_high must be finite",
    ):
        engine.detect(
            previous_high=118_000,
            previous_low=116_000,
            current_high=invalid_value,
            current_low=116_500,
        )


@pytest.mark.parametrize(
    "invalid_value",
    [
        "118000",
        None,
        True,
        False,
    ],
)
def test_rejects_non_numeric_prices(
    engine: BOSEngine,
    invalid_value: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="previous_high must be a number",
    ):
        engine.detect(
            previous_high=invalid_value,  # type: ignore[arg-type]
            previous_low=116_000,
            current_high=118_600,
            current_low=116_500,
        )


def test_rejects_invalid_previous_range(
    engine: BOSEngine,
) -> None:
    with pytest.raises(
        ValueError,
        match="previous_high must be greater than previous_low",
    ):
        engine.detect(
            previous_high=116_000,
            previous_low=118_000,
            current_high=118_600,
            current_low=116_500,
        )


def test_rejects_equal_previous_high_and_low(
    engine: BOSEngine,
) -> None:
    with pytest.raises(
        ValueError,
        match="previous_high must be greater than previous_low",
    ):
        engine.detect(
            previous_high=118_000,
            previous_low=118_000,
            current_high=118_600,
            current_low=116_500,
        )


def test_rejects_invalid_current_range(
    engine: BOSEngine,
) -> None:
    with pytest.raises(
        ValueError,
        match=(
            "current_high must be greater than or equal "
            "to current_low"
        ),
    ):
        engine.detect(
            previous_high=118_000,
            previous_low=116_000,
            current_high=115_000,
            current_low=116_500,
        )


def test_accepts_zero_range_current_observation(
    engine: BOSEngine,
) -> None:
    result = engine.detect(
        previous_high=118_000,
        previous_low=116_000,
        current_high=117_000,
        current_low=117_000,
    )

    assert result.bullish_bos is False
    assert result.bearish_bos is False
    assert result.breakout_price is None


def test_bos_result_is_immutable() -> None:
    result = BOSResult(
        bullish_bos=True,
        bearish_bos=False,
        breakout_price=118_600,
    )

    with pytest.raises(AttributeError):
        result.breakout_price = 120_000  # type: ignore[misc]