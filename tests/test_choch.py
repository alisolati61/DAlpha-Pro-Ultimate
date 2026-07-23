import math

import pytest

from src.analysis.smart_money.choch import (
    CHOCHEngine,
    CHOCHResult,
)


@pytest.fixture
def engine() -> CHOCHEngine:
    return CHOCHEngine()


def test_detects_bullish_choch(
    engine: CHOCHEngine,
) -> None:
    result = engine.detect(
        previous_trend="BEARISH",
        previous_high=118_000,
        current_high=118_800,
        previous_low=116_000,
        current_low=116_300,
    )

    assert result == CHOCHResult(
        bullish_choch=True,
        bearish_choch=False,
        reversal_price=118_800.0,
    )


def test_detects_bearish_choch(
    engine: CHOCHEngine,
) -> None:
    result = engine.detect(
        previous_trend="BULLISH",
        previous_high=118_000,
        current_high=117_700,
        previous_low=116_000,
        current_low=115_500,
    )

    assert result == CHOCHResult(
        bullish_choch=False,
        bearish_choch=True,
        reversal_price=115_500.0,
    )


def test_returns_no_choch_in_bearish_trend_without_high_break(
    engine: CHOCHEngine,
) -> None:
    result = engine.detect(
        previous_trend="BEARISH",
        previous_high=118_000,
        current_high=117_900,
        previous_low=116_000,
        current_low=115_500,
    )

    assert result == CHOCHResult(
        bullish_choch=False,
        bearish_choch=False,
        reversal_price=None,
    )


def test_returns_no_choch_in_bullish_trend_without_low_break(
    engine: CHOCHEngine,
) -> None:
    result = engine.detect(
        previous_trend="BULLISH",
        previous_high=118_000,
        current_high=118_500,
        previous_low=116_000,
        current_low=116_100,
    )

    assert result == CHOCHResult(
        bullish_choch=False,
        bearish_choch=False,
        reversal_price=None,
    )


def test_equal_high_is_not_bullish_choch(
    engine: CHOCHEngine,
) -> None:
    result = engine.detect(
        previous_trend="BEARISH",
        previous_high=118_000,
        current_high=118_000,
        previous_low=116_000,
        current_low=116_300,
    )

    assert result.bullish_choch is False
    assert result.bearish_choch is False
    assert result.reversal_price is None


def test_equal_low_is_not_bearish_choch(
    engine: CHOCHEngine,
) -> None:
    result = engine.detect(
        previous_trend="BULLISH",
        previous_high=118_000,
        current_high=117_800,
        previous_low=116_000,
        current_low=116_000,
    )

    assert result.bullish_choch is False
    assert result.bearish_choch is False
    assert result.reversal_price is None


def test_bearish_trend_ignores_downward_break(
    engine: CHOCHEngine,
) -> None:
    result = engine.detect(
        previous_trend="BEARISH",
        previous_high=118_000,
        current_high=117_500,
        previous_low=116_000,
        current_low=115_500,
    )

    assert result.bullish_choch is False
    assert result.bearish_choch is False
    assert result.reversal_price is None


def test_bullish_trend_ignores_upward_break(
    engine: CHOCHEngine,
) -> None:
    result = engine.detect(
        previous_trend="BULLISH",
        previous_high=118_000,
        current_high=118_500,
        previous_low=116_000,
        current_low=116_300,
    )

    assert result.bullish_choch is False
    assert result.bearish_choch is False
    assert result.reversal_price is None


def test_normalizes_lowercase_trend(
    engine: CHOCHEngine,
) -> None:
    result = engine.detect(
        previous_trend=" bearish ",
        previous_high=118_000,
        current_high=118_800,
        previous_low=116_000,
        current_low=116_300,
    )

    assert result.bullish_choch is True
    assert result.bearish_choch is False
    assert result.reversal_price == pytest.approx(118_800.0)


@pytest.mark.parametrize(
    "invalid_trend",
    [
        "",
        "SIDEWAYS",
        "NEUTRAL",
        "UP",
        "DOWN",
    ],
)
def test_rejects_invalid_trend(
    engine: CHOCHEngine,
    invalid_trend: str,
) -> None:
    with pytest.raises(
        ValueError,
        match=(
            "previous_trend must be either "
            "BULLISH or BEARISH"
        ),
    ):
        engine.detect(
            previous_trend=invalid_trend,
            previous_high=118_000,
            current_high=118_800,
            previous_low=116_000,
            current_low=116_300,
        )


@pytest.mark.parametrize(
    "invalid_trend",
    [
        None,
        1,
        True,
        [],
    ],
)
def test_rejects_non_string_trend(
    engine: CHOCHEngine,
    invalid_trend: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="previous_trend must be a string",
    ):
        engine.detect(
            previous_trend=invalid_trend,  # type: ignore[arg-type]
            previous_high=118_000,
            current_high=118_800,
            previous_low=116_000,
            current_low=116_300,
        )


@pytest.mark.parametrize(
    "invalid_price",
    [
        0,
        -1,
        -100.5,
    ],
)
def test_rejects_non_positive_prices(
    engine: CHOCHEngine,
    invalid_price: float,
) -> None:
    with pytest.raises(
        ValueError,
        match="current_high must be greater than zero",
    ):
        engine.detect(
            previous_trend="BEARISH",
            previous_high=118_000,
            current_high=invalid_price,
            previous_low=116_000,
            current_low=116_300,
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
    engine: CHOCHEngine,
    invalid_price: float,
) -> None:
    with pytest.raises(
        ValueError,
        match="previous_low must be finite",
    ):
        engine.detect(
            previous_trend="BEARISH",
            previous_high=118_000,
            current_high=118_800,
            previous_low=invalid_price,
            current_low=116_300,
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
    engine: CHOCHEngine,
    invalid_price: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="previous_high must be a number",
    ):
        engine.detect(
            previous_trend="BEARISH",
            previous_high=invalid_price,  # type: ignore[arg-type]
            current_high=118_800,
            previous_low=116_000,
            current_low=116_300,
        )


def test_rejects_invalid_previous_structure(
    engine: CHOCHEngine,
) -> None:
    with pytest.raises(
        ValueError,
        match="previous_high must be greater than previous_low",
    ):
        engine.detect(
            previous_trend="BEARISH",
            previous_high=116_000,
            current_high=118_800,
            previous_low=118_000,
            current_low=116_300,
        )


def test_rejects_equal_previous_high_and_low(
    engine: CHOCHEngine,
) -> None:
    with pytest.raises(
        ValueError,
        match="previous_high must be greater than previous_low",
    ):
        engine.detect(
            previous_trend="BEARISH",
            previous_high=118_000,
            current_high=118_800,
            previous_low=118_000,
            current_low=116_300,
        )


def test_rejects_invalid_current_range(
    engine: CHOCHEngine,
) -> None:
    with pytest.raises(
        ValueError,
        match=(
            "current_high must be greater than or equal "
            "to current_low"
        ),
    ):
        engine.detect(
            previous_trend="BEARISH",
            previous_high=118_000,
            current_high=115_000,
            previous_low=116_000,
            current_low=116_300,
        )


def test_accepts_zero_range_current_observation(
    engine: CHOCHEngine,
) -> None:
    result = engine.detect(
        previous_trend="BULLISH",
        previous_high=118_000,
        current_high=117_000,
        previous_low=116_000,
        current_low=117_000,
    )

    assert result.bullish_choch is False
    assert result.bearish_choch is False
    assert result.reversal_price is None


def test_result_is_immutable() -> None:
    result = CHOCHResult(
        bullish_choch=True,
        bearish_choch=False,
        reversal_price=118_800.0,
    )

    with pytest.raises(AttributeError):
        result.reversal_price = 120_000  # type: ignore[misc]