"""Tests for smart-money order-block mitigation detection."""

from dataclasses import FrozenInstanceError
from math import inf, nan

import pytest

from src.analysis.smart_money.mitigation import (
    MitigationEngine,
    MitigationResult,
)
from src.analysis.smart_money.order_block import OrderBlock


def bullish_order_block() -> OrderBlock:
    return OrderBlock(
        bullish=True,
        bearish=False,
        high=110.0,
        low=100.0,
        valid=True,
    )


def bearish_order_block() -> OrderBlock:
    return OrderBlock(
        bullish=False,
        bearish=True,
        high=110.0,
        low=100.0,
        valid=True,
    )


def test_default_configuration() -> None:
    engine = MitigationEngine()

    assert engine.minimum_penetration == 0.5
    assert engine.invalidation_mode == "close"


@pytest.mark.parametrize("value", [-0.01, 1.01])
def test_rejects_out_of_range_minimum_penetration(
    value: float,
) -> None:
    with pytest.raises(
        ValueError,
        match="minimum_penetration must be between",
    ):
        MitigationEngine(minimum_penetration=value)


@pytest.mark.parametrize("value", ["0.5", None, True, object()])
def test_rejects_non_numeric_minimum_penetration(
    value: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="minimum_penetration must be a real number",
    ):
        MitigationEngine(minimum_penetration=value)  # type: ignore[arg-type]


@pytest.mark.parametrize("value", [nan, inf, -inf])
def test_rejects_non_finite_minimum_penetration(
    value: float,
) -> None:
    with pytest.raises(
        ValueError,
        match="minimum_penetration must be finite",
    ):
        MitigationEngine(minimum_penetration=value)


def test_rejects_unknown_invalidation_mode() -> None:
    with pytest.raises(
        ValueError,
        match="invalidation_mode must be either",
    ):
        MitigationEngine(
            invalidation_mode="unknown",  # type: ignore[arg-type]
        )


def test_bullish_zone_not_touched() -> None:
    result = MitigationEngine().evaluate(
        bullish_order_block(),
        candle_high=115.0,
        candle_low=111.0,
        candle_close=113.0,
    )

    assert result.bullish is True
    assert result.bearish is False
    assert result.touched is False
    assert result.mitigated is False
    assert result.invalidated is False
    assert result.penetration_ratio == 0.0


def test_bearish_zone_not_touched() -> None:
    result = MitigationEngine().evaluate(
        bearish_order_block(),
        candle_high=99.0,
        candle_low=95.0,
        candle_close=97.0,
    )

    assert result.touched is False
    assert result.mitigated is False
    assert result.invalidated is False
    assert result.penetration_ratio == 0.0


def test_bullish_zone_touched_but_below_threshold() -> None:
    result = MitigationEngine(
        minimum_penetration=0.5,
    ).evaluate(
        bullish_order_block(),
        candle_high=114.0,
        candle_low=108.0,
        candle_close=112.0,
    )

    assert result.touched is True
    assert result.mitigated is False
    assert result.invalidated is False
    assert result.penetration_ratio == pytest.approx(0.2)


def test_bullish_zone_mitigated_at_threshold() -> None:
    result = MitigationEngine(
        minimum_penetration=0.5,
    ).evaluate(
        bullish_order_block(),
        candle_high=114.0,
        candle_low=105.0,
        candle_close=108.0,
    )

    assert result.touched is True
    assert result.mitigated is True
    assert result.invalidated is False
    assert result.penetration_ratio == pytest.approx(0.5)


def test_bearish_zone_mitigated_at_threshold() -> None:
    result = MitigationEngine(
        minimum_penetration=0.5,
    ).evaluate(
        bearish_order_block(),
        candle_high=105.0,
        candle_low=96.0,
        candle_close=102.0,
    )

    assert result.touched is True
    assert result.mitigated is True
    assert result.invalidated is False
    assert result.penetration_ratio == pytest.approx(0.5)


def test_bullish_full_penetration_is_capped_at_one() -> None:
    result = MitigationEngine(
        invalidation_mode="close",
    ).evaluate(
        bullish_order_block(),
        candle_high=112.0,
        candle_low=95.0,
        candle_close=105.0,
    )

    assert result.penetration_ratio == 1.0
    assert result.fully_mitigated is True
    assert result.invalidated is False


def test_bearish_full_penetration_is_capped_at_one() -> None:
    result = MitigationEngine(
        invalidation_mode="close",
    ).evaluate(
        bearish_order_block(),
        candle_high=115.0,
        candle_low=98.0,
        candle_close=105.0,
    )

    assert result.penetration_ratio == 1.0
    assert result.fully_mitigated is True
    assert result.invalidated is False


def test_bullish_close_invalidation() -> None:
    result = MitigationEngine(
        invalidation_mode="close",
    ).evaluate(
        bullish_order_block(),
        candle_high=108.0,
        candle_low=95.0,
        candle_close=99.0,
    )

    assert result.touched is True
    assert result.invalidated is True
    assert result.mitigated is False
    assert result.penetration_ratio == 1.0


def test_bearish_close_invalidation() -> None:
    result = MitigationEngine(
        invalidation_mode="close",
    ).evaluate(
        bearish_order_block(),
        candle_high=115.0,
        candle_low=102.0,
        candle_close=111.0,
    )

    assert result.touched is True
    assert result.invalidated is True
    assert result.mitigated is False
    assert result.penetration_ratio == 1.0


def test_bullish_wick_invalidation() -> None:
    result = MitigationEngine(
        invalidation_mode="wick",
    ).evaluate(
        bullish_order_block(),
        candle_high=108.0,
        candle_low=99.0,
        candle_close=105.0,
    )

    assert result.invalidated is True
    assert result.mitigated is False


def test_bearish_wick_invalidation() -> None:
    result = MitigationEngine(
        invalidation_mode="wick",
    ).evaluate(
        bearish_order_block(),
        candle_high=111.0,
        candle_low=102.0,
        candle_close=105.0,
    )

    assert result.invalidated is True
    assert result.mitigated is False


def test_boundary_touch_is_detected() -> None:
    bullish = MitigationEngine(
        minimum_penetration=0.0,
    ).evaluate(
        bullish_order_block(),
        candle_high=115.0,
        candle_low=110.0,
        candle_close=112.0,
    )

    bearish = MitigationEngine(
        minimum_penetration=0.0,
    ).evaluate(
        bearish_order_block(),
        candle_high=100.0,
        candle_low=95.0,
        candle_close=98.0,
    )

    assert bullish.touched is True
    assert bullish.penetration_ratio == 0.0
    assert bullish.mitigated is True

    assert bearish.touched is True
    assert bearish.penetration_ratio == 0.0
    assert bearish.mitigated is True


def test_result_properties() -> None:
    result = MitigationEngine().evaluate(
        bullish_order_block(),
        candle_high=112.0,
        candle_low=104.0,
        candle_close=108.0,
    )

    assert result.direction == "bullish"
    assert result.zone_size == 10.0
    assert result.fully_mitigated is False


def test_result_is_immutable() -> None:
    result = MitigationEngine().evaluate(
        bullish_order_block(),
        candle_high=112.0,
        candle_low=105.0,
        candle_close=108.0,
    )

    with pytest.raises(FrozenInstanceError):
        result.mitigated = False  # type: ignore[misc]


def test_rejects_non_order_block() -> None:
    with pytest.raises(
        TypeError,
        match="order_block must be an OrderBlock instance",
    ):
        MitigationEngine().evaluate(
            object(),  # type: ignore[arg-type]
            candle_high=110.0,
            candle_low=100.0,
            candle_close=105.0,
        )


def test_rejects_invalid_order_block() -> None:
    invalid = OrderBlock(
        bullish=False,
        bearish=False,
        high=110.0,
        low=100.0,
        valid=False,
    )

    with pytest.raises(
        ValueError,
        match="order_block must be valid",
    ):
        MitigationEngine().evaluate(
            invalid,
            candle_high=110.0,
            candle_low=100.0,
            candle_close=105.0,
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("candle_high", "110"),
        ("candle_low", None),
        ("candle_close", True),
    ],
)
def test_rejects_non_numeric_candle_values(
    field: str,
    value: object,
) -> None:
    candle = {
        "candle_high": 110.0,
        "candle_low": 100.0,
        "candle_close": 105.0,
    }
    candle[field] = value

    with pytest.raises(TypeError, match=f"{field} must be a real number"):
        MitigationEngine().evaluate(
            bullish_order_block(),
            **candle,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("candle_high", nan),
        ("candle_low", inf),
        ("candle_close", -inf),
    ],
)
def test_rejects_non_finite_candle_values(
    field: str,
    value: float,
) -> None:
    candle = {
        "candle_high": 110.0,
        "candle_low": 100.0,
        "candle_close": 105.0,
    }
    candle[field] = value

    with pytest.raises(ValueError, match=f"{field} must be finite"):
        MitigationEngine().evaluate(
            bullish_order_block(),
            **candle,
        )


def test_rejects_high_below_low() -> None:
    with pytest.raises(
        ValueError,
        match="candle_high must be greater than or equal",
    ):
        MitigationEngine().evaluate(
            bullish_order_block(),
            candle_high=99.0,
            candle_low=100.0,
            candle_close=99.5,
        )


def test_rejects_close_above_high() -> None:
    with pytest.raises(
        ValueError,
        match="candle_close cannot be above candle_high",
    ):
        MitigationEngine().evaluate(
            bullish_order_block(),
            candle_high=110.0,
            candle_low=100.0,
            candle_close=111.0,
        )


def test_rejects_close_below_low() -> None:
    with pytest.raises(
        ValueError,
        match="candle_close cannot be below candle_low",
    ):
        MitigationEngine().evaluate(
            bullish_order_block(),
            candle_high=110.0,
            candle_low=100.0,
            candle_close=99.0,
        )


def test_result_rejects_conflicting_direction() -> None:
    with pytest.raises(
        ValueError,
        match="exactly one of bullish or bearish must be true",
    ):
        MitigationResult(
            bullish=True,
            bearish=True,
            zone_high=110.0,
            zone_low=100.0,
            touched=True,
            mitigated=False,
            invalidated=False,
            penetration_ratio=0.5,
        )


def test_result_rejects_mitigated_without_touch() -> None:
    with pytest.raises(
        ValueError,
        match="a mitigated zone must also be touched",
    ):
        MitigationResult(
            bullish=True,
            bearish=False,
            zone_high=110.0,
            zone_low=100.0,
            touched=False,
            mitigated=True,
            invalidated=False,
            penetration_ratio=0.0,
        )


def test_result_rejects_mitigated_and_invalidated() -> None:
    with pytest.raises(
        ValueError,
        match="cannot be both mitigated and invalidated",
    ):
        MitigationResult(
            bullish=True,
            bearish=False,
            zone_high=110.0,
            zone_low=100.0,
            touched=True,
            mitigated=True,
            invalidated=True,
            penetration_ratio=1.0,
        )