from dataclasses import FrozenInstanceError

import pytest

from src.analysis.smart_money.order_block import (
    OrderBlock,
    OrderBlockEngine,
)


@pytest.fixture
def engine() -> OrderBlockEngine:
    return OrderBlockEngine()


def test_detects_bullish_candidate(
    engine: OrderBlockEngine,
) -> None:
    result = engine.detect(
        candle_open=117_800,
        candle_close=118_500,
        candle_high=118_700,
        candle_low=117_500,
    )

    assert result.bullish is True
    assert result.bearish is False
    assert result.valid is True
    assert result.direction == "bullish"
    assert result.high == 118_700.0
    assert result.low == 117_500.0


def test_detects_bearish_candidate(
    engine: OrderBlockEngine,
) -> None:
    result = engine.detect(
        candle_open=118_500,
        candle_close=117_800,
        candle_high=118_700,
        candle_low=117_500,
    )

    assert result.bullish is False
    assert result.bearish is True
    assert result.valid is True
    assert result.direction == "bearish"


def test_doji_is_not_a_valid_candidate(
    engine: OrderBlockEngine,
) -> None:
    result = engine.detect(
        candle_open=100,
        candle_close=100,
        candle_high=105,
        candle_low=95,
    )

    assert result.bullish is False
    assert result.bearish is False
    assert result.valid is False
    assert result.direction is None


def test_open_and_close_may_equal_high_and_low(
    engine: OrderBlockEngine,
) -> None:
    result = engine.detect(
        candle_open=100,
        candle_close=110,
        candle_high=110,
        candle_low=100,
    )

    assert result.bullish is True
    assert result.valid is True


def test_zero_range_doji_is_allowed_but_invalid(
    engine: OrderBlockEngine,
) -> None:
    result = engine.detect(
        candle_open=100,
        candle_close=100,
        candle_high=100,
        candle_low=100,
    )

    assert result.valid is False
    assert result.range_size == 0.0
    assert result.midpoint == 100.0


def test_range_size(
    engine: OrderBlockEngine,
) -> None:
    result = engine.detect(
        candle_open=100,
        candle_close=105,
        candle_high=108,
        candle_low=96,
    )

    assert result.range_size == 12.0


def test_midpoint(
    engine: OrderBlockEngine,
) -> None:
    result = engine.detect(
        candle_open=100,
        candle_close=105,
        candle_high=110,
        candle_low=90,
    )

    assert result.midpoint == 100.0


@pytest.mark.parametrize(
    ("field_name", "field_value"),
    [
        ("candle_open", "100"),
        ("candle_close", None),
        ("candle_high", object()),
        ("candle_low", True),
    ],
)
def test_rejects_non_numeric_values(
    engine: OrderBlockEngine,
    field_name: str,
    field_value: object,
) -> None:
    candle = {
        "candle_open": 100,
        "candle_close": 105,
        "candle_high": 110,
        "candle_low": 95,
    }
    candle[field_name] = field_value

    with pytest.raises(TypeError, match=field_name):
        engine.detect(**candle)


@pytest.mark.parametrize(
    ("field_name", "field_value"),
    [
        ("candle_open", float("nan")),
        ("candle_close", float("inf")),
        ("candle_high", float("-inf")),
        ("candle_low", float("nan")),
    ],
)
def test_rejects_non_finite_values(
    engine: OrderBlockEngine,
    field_name: str,
    field_value: float,
) -> None:
    candle = {
        "candle_open": 100,
        "candle_close": 105,
        "candle_high": 110,
        "candle_low": 95,
    }
    candle[field_name] = field_value

    with pytest.raises(ValueError, match=field_name):
        engine.detect(**candle)


def test_rejects_high_below_low(
    engine: OrderBlockEngine,
) -> None:
    with pytest.raises(
        ValueError,
        match="candle_high must be greater",
    ):
        engine.detect(
            candle_open=100,
            candle_close=105,
            candle_high=90,
            candle_low=95,
        )


def test_rejects_high_below_open(
    engine: OrderBlockEngine,
) -> None:
    with pytest.raises(
        ValueError,
        match="candle_high cannot be below",
    ):
        engine.detect(
            candle_open=110,
            candle_close=100,
            candle_high=105,
            candle_low=95,
        )


def test_rejects_high_below_close(
    engine: OrderBlockEngine,
) -> None:
    with pytest.raises(
        ValueError,
        match="candle_high cannot be below",
    ):
        engine.detect(
            candle_open=100,
            candle_close=110,
            candle_high=105,
            candle_low=95,
        )


def test_rejects_low_above_open(
    engine: OrderBlockEngine,
) -> None:
    with pytest.raises(
        ValueError,
        match="candle_low cannot be above",
    ):
        engine.detect(
            candle_open=100,
            candle_close=110,
            candle_high=115,
            candle_low=105,
        )


def test_rejects_low_above_close(
    engine: OrderBlockEngine,
) -> None:
    with pytest.raises(
        ValueError,
        match="candle_low cannot be above",
    ):
        engine.detect(
            candle_open=110,
            candle_close=100,
            candle_high=115,
            candle_low=105,
        )


def test_result_is_immutable(
    engine: OrderBlockEngine,
) -> None:
    result = engine.detect(
        candle_open=100,
        candle_close=105,
        candle_high=110,
        candle_low=95,
    )

    with pytest.raises(FrozenInstanceError):
        result.high = 120  # type: ignore[misc]


def test_order_block_rejects_both_directions() -> None:
    with pytest.raises(
        ValueError,
        match="cannot be both bullish and bearish",
    ):
        OrderBlock(
            bullish=True,
            bearish=True,
            high=110,
            low=90,
            valid=False,
        )


def test_order_block_rejects_inconsistent_valid_flag() -> None:
    with pytest.raises(
        ValueError,
        match="valid must be true",
    ):
        OrderBlock(
            bullish=True,
            bearish=False,
            high=110,
            low=90,
            valid=False,
        )


def test_order_block_rejects_directionless_valid_result() -> None:
    with pytest.raises(
        ValueError,
        match="valid must be true",
    ):
        OrderBlock(
            bullish=False,
            bearish=False,
            high=110,
            low=90,
            valid=True,
        )


def test_order_block_rejects_invalid_range() -> None:
    with pytest.raises(
        ValueError,
        match="high must be greater",
    ):
        OrderBlock(
            bullish=True,
            bearish=False,
            high=90,
            low=110,
            valid=True,
        )