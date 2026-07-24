"""Tests for smart-money breaker-block detection and retests."""

from dataclasses import FrozenInstanceError
from math import inf, nan

import pytest

from src.analysis.smart_money.bos import BOSResult
from src.analysis.smart_money.breaker_block import (
    BreakerBlock,
    BreakerBlockEngine,
    BreakerRetestResult,
)
from src.analysis.smart_money.mitigation import MitigationResult
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


def invalidated_mitigation(
    order_block: OrderBlock,
) -> MitigationResult:
    return MitigationResult(
        bullish=order_block.bullish,
        bearish=order_block.bearish,
        zone_high=order_block.high,
        zone_low=order_block.low,
        touched=True,
        mitigated=False,
        invalidated=True,
        penetration_ratio=1.0,
    )


def non_invalidated_mitigation(
    order_block: OrderBlock,
) -> MitigationResult:
    return MitigationResult(
        bullish=order_block.bullish,
        bearish=order_block.bearish,
        zone_high=order_block.high,
        zone_low=order_block.low,
        touched=True,
        mitigated=True,
        invalidated=False,
        penetration_ratio=0.5,
    )


def bullish_bos(price: float = 115.0) -> BOSResult:
    return BOSResult(
        bullish_bos=True,
        bearish_bos=False,
        breakout_price=price,
    )


def bearish_bos(price: float = 95.0) -> BOSResult:
    return BOSResult(
        bullish_bos=False,
        bearish_bos=True,
        breakout_price=price,
    )


def no_bos() -> BOSResult:
    return BOSResult(
        bullish_bos=False,
        bearish_bos=False,
        breakout_price=None,
    )


def ambiguous_bos() -> BOSResult:
    return BOSResult(
        bullish_bos=True,
        bearish_bos=True,
        breakout_price=None,
    )


def bullish_breaker() -> BreakerBlock:
    return BreakerBlockEngine().detect(
        bearish_order_block(),
        invalidated_mitigation(bearish_order_block()),
        bullish_bos(),
    )


def bearish_breaker() -> BreakerBlock:
    return BreakerBlockEngine().detect(
        bullish_order_block(),
        invalidated_mitigation(bullish_order_block()),
        bearish_bos(),
    )


def test_default_configuration() -> None:
    engine = BreakerBlockEngine()

    assert engine.minimum_retest_penetration == 0.0
    assert engine.invalidation_mode == "close"


@pytest.mark.parametrize("value", [-0.01, 1.01])
def test_rejects_out_of_range_retest_penetration(
    value: float,
) -> None:
    with pytest.raises(
        ValueError,
        match="minimum_retest_penetration must be between",
    ):
        BreakerBlockEngine(minimum_retest_penetration=value)


@pytest.mark.parametrize("value", ["0.5", None, True, object()])
def test_rejects_non_numeric_retest_penetration(
    value: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="minimum_retest_penetration must be a real number",
    ):
        BreakerBlockEngine(
            minimum_retest_penetration=value,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize("value", [nan, inf, -inf])
def test_rejects_non_finite_retest_penetration(
    value: float,
) -> None:
    with pytest.raises(
        ValueError,
        match="minimum_retest_penetration must be finite",
    ):
        BreakerBlockEngine(minimum_retest_penetration=value)


def test_rejects_unknown_invalidation_mode() -> None:
    with pytest.raises(
        ValueError,
        match="invalidation_mode must be either",
    ):
        BreakerBlockEngine(
            invalidation_mode="unknown",  # type: ignore[arg-type]
        )


def test_detects_bullish_breaker() -> None:
    block = bearish_order_block()

    result = BreakerBlockEngine().detect(
        block,
        invalidated_mitigation(block),
        bullish_bos(),
    )

    assert result.confirmed is True
    assert result.bullish is True
    assert result.bearish is False
    assert result.direction == "bullish"
    assert result.zone_high == 110.0
    assert result.zone_low == 100.0
    assert result.breakout_price == 115.0


def test_detects_bearish_breaker() -> None:
    block = bullish_order_block()

    result = BreakerBlockEngine().detect(
        block,
        invalidated_mitigation(block),
        bearish_bos(),
    )

    assert result.confirmed is True
    assert result.bullish is False
    assert result.bearish is True
    assert result.direction == "bearish"
    assert result.breakout_price == 95.0


@pytest.mark.parametrize(
    ("block", "bos"),
    [
        (bullish_order_block(), bullish_bos()),
        (bearish_order_block(), bearish_bos()),
    ],
)
def test_same_direction_bos_does_not_form_breaker(
    block: OrderBlock,
    bos: BOSResult,
) -> None:
    result = BreakerBlockEngine().detect(
        block,
        invalidated_mitigation(block),
        bos,
    )

    assert result.confirmed is False
    assert result.direction is None
    assert result.breakout_price is None


@pytest.mark.parametrize("bos", [no_bos(), ambiguous_bos()])
def test_missing_or_ambiguous_bos_does_not_form_breaker(
    bos: BOSResult,
) -> None:
    block = bearish_order_block()

    result = BreakerBlockEngine().detect(
        block,
        invalidated_mitigation(block),
        bos,
    )

    assert result.confirmed is False


def test_non_invalidated_order_block_does_not_form_breaker() -> None:
    block = bearish_order_block()

    result = BreakerBlockEngine().detect(
        block,
        non_invalidated_mitigation(block),
        bullish_bos(),
    )

    assert result.confirmed is False


@pytest.mark.parametrize(
    ("block", "bos"),
    [
        (bearish_order_block(), bullish_bos(110.0)),
        (bearish_order_block(), bullish_bos(109.0)),
        (bullish_order_block(), bearish_bos(100.0)),
        (bullish_order_block(), bearish_bos(101.0)),
    ],
)
def test_bos_must_break_beyond_entire_zone(
    block: OrderBlock,
    bos: BOSResult,
) -> None:
    result = BreakerBlockEngine().detect(
        block,
        invalidated_mitigation(block),
        bos,
    )

    assert result.confirmed is False


def test_breaker_properties() -> None:
    result = bullish_breaker()

    assert result.zone_size == 10.0
    assert result.midpoint == 105.0


def test_breaker_is_immutable() -> None:
    result = bullish_breaker()

    with pytest.raises(FrozenInstanceError):
        result.confirmed = False  # type: ignore[misc]


@pytest.mark.parametrize(
    ("argument", "value", "message"),
    [
        (
            "order_block",
            object(),
            "order_block must be an OrderBlock instance",
        ),
        (
            "mitigation",
            object(),
            "mitigation must be a MitigationResult instance",
        ),
        ("bos", object(), "bos must be a BOSResult instance"),
    ],
)
def test_rejects_invalid_dependency_types(
    argument: str,
    value: object,
    message: str,
) -> None:
    values: dict[str, object] = {
        "order_block": bearish_order_block(),
        "mitigation": invalidated_mitigation(
            bearish_order_block()
        ),
        "bos": bullish_bos(),
    }
    values[argument] = value

    with pytest.raises(TypeError, match=message):
        BreakerBlockEngine().detect(**values)  # type: ignore[arg-type]


def test_rejects_mitigation_direction_mismatch() -> None:
    block = bearish_order_block()
    mitigation = MitigationResult(
        bullish=True,
        bearish=False,
        zone_high=110.0,
        zone_low=100.0,
        touched=True,
        mitigated=False,
        invalidated=True,
        penetration_ratio=1.0,
    )

    with pytest.raises(
        ValueError,
        match="mitigation direction must match",
    ):
        BreakerBlockEngine().detect(
            block,
            mitigation,
            bullish_bos(),
        )


@pytest.mark.parametrize(
    ("zone_high", "zone_low", "message"),
    [
        (111.0, 100.0, "mitigation zone_high must match"),
        (110.0, 99.0, "mitigation zone_low must match"),
    ],
)
def test_rejects_mitigation_zone_mismatch(
    zone_high: float,
    zone_low: float,
    message: str,
) -> None:
    block = bearish_order_block()
    mitigation = MitigationResult(
        bullish=False,
        bearish=True,
        zone_high=zone_high,
        zone_low=zone_low,
        touched=True,
        mitigated=False,
        invalidated=True,
        penetration_ratio=1.0,
    )

    with pytest.raises(ValueError, match=message):
        BreakerBlockEngine().detect(
            block,
            mitigation,
            bullish_bos(),
        )


def test_directional_bos_requires_breakout_price() -> None:
    block = bearish_order_block()
    broken_bos = BOSResult(
        bullish_bos=True,
        bearish_bos=False,
        breakout_price=None,
    )

    with pytest.raises(
        ValueError,
        match="directional BOS must have breakout_price",
    ):
        BreakerBlockEngine().detect(
            block,
            invalidated_mitigation(block),
            broken_bos,
        )


def test_bos_without_direction_cannot_have_price() -> None:
    block = bearish_order_block()
    broken_bos = BOSResult(
        bullish_bos=False,
        bearish_bos=False,
        breakout_price=115.0,
    )

    with pytest.raises(
        ValueError,
        match="BOS without direction cannot have breakout_price",
    ):
        BreakerBlockEngine().detect(
            block,
            invalidated_mitigation(block),
            broken_bos,
        )


def test_bullish_retest_not_touched() -> None:
    result = BreakerBlockEngine().evaluate_retest(
        bullish_breaker(),
        candle_high=120.0,
        candle_low=111.0,
        candle_close=115.0,
    )

    assert result.touched is False
    assert result.rejected is False
    assert result.invalidated is False
    assert result.penetration_ratio == 0.0


def test_bearish_retest_not_touched() -> None:
    result = BreakerBlockEngine().evaluate_retest(
        bearish_breaker(),
        candle_high=99.0,
        candle_low=90.0,
        candle_close=95.0,
    )

    assert result.touched is False
    assert result.rejected is False
    assert result.invalidated is False
    assert result.penetration_ratio == 0.0


def test_bullish_retest_rejection() -> None:
    result = BreakerBlockEngine(
        minimum_retest_penetration=0.5,
    ).evaluate_retest(
        bullish_breaker(),
        candle_high=114.0,
        candle_low=105.0,
        candle_close=112.0,
    )

    assert result.touched is True
    assert result.rejected is True
    assert result.invalidated is False
    assert result.penetration_ratio == pytest.approx(0.5)


def test_bearish_retest_rejection() -> None:
    result = BreakerBlockEngine(
        minimum_retest_penetration=0.5,
    ).evaluate_retest(
        bearish_breaker(),
        candle_high=105.0,
        candle_low=96.0,
        candle_close=98.0,
    )

    assert result.touched is True
    assert result.rejected is True
    assert result.invalidated is False
    assert result.penetration_ratio == pytest.approx(0.5)


def test_touch_without_expected_close_is_not_rejection() -> None:
    result = BreakerBlockEngine().evaluate_retest(
        bullish_breaker(),
        candle_high=109.0,
        candle_low=105.0,
        candle_close=108.0,
    )

    assert result.touched is True
    assert result.rejected is False
    assert result.invalidated is False


def test_bullish_close_invalidation() -> None:
    result = BreakerBlockEngine(
        invalidation_mode="close",
    ).evaluate_retest(
        bullish_breaker(),
        candle_high=108.0,
        candle_low=95.0,
        candle_close=99.0,
    )

    assert result.invalidated is True
    assert result.rejected is False
    assert result.penetration_ratio == 1.0


def test_bearish_close_invalidation() -> None:
    result = BreakerBlockEngine(
        invalidation_mode="close",
    ).evaluate_retest(
        bearish_breaker(),
        candle_high=115.0,
        candle_low=102.0,
        candle_close=111.0,
    )

    assert result.invalidated is True
    assert result.rejected is False


def test_bullish_wick_invalidation() -> None:
    result = BreakerBlockEngine(
        invalidation_mode="wick",
    ).evaluate_retest(
        bullish_breaker(),
        candle_high=112.0,
        candle_low=99.0,
        candle_close=111.0,
    )

    assert result.invalidated is True
    assert result.rejected is False


def test_bearish_wick_invalidation() -> None:
    result = BreakerBlockEngine(
        invalidation_mode="wick",
    ).evaluate_retest(
        bearish_breaker(),
        candle_high=111.0,
        candle_low=98.0,
        candle_close=99.0,
    )

    assert result.invalidated is True
    assert result.rejected is False


def test_retest_requires_confirmed_breaker() -> None:
    unconfirmed = BreakerBlock(
        bullish=False,
        bearish=False,
        zone_high=110.0,
        zone_low=100.0,
        confirmed=False,
        breakout_price=None,
    )

    with pytest.raises(ValueError, match="breaker must be confirmed"):
        BreakerBlockEngine().evaluate_retest(
            unconfirmed,
            candle_high=112.0,
            candle_low=105.0,
            candle_close=111.0,
        )


def test_retest_rejects_non_breaker() -> None:
    with pytest.raises(
        TypeError,
        match="breaker must be a BreakerBlock instance",
    ):
        BreakerBlockEngine().evaluate_retest(
            object(),  # type: ignore[arg-type]
            candle_high=112.0,
            candle_low=105.0,
            candle_close=111.0,
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("candle_high", "112"),
        ("candle_low", None),
        ("candle_close", True),
    ],
)
def test_retest_rejects_non_numeric_prices(
    field: str,
    value: object,
) -> None:
    candle: dict[str, object] = {
        "candle_high": 112.0,
        "candle_low": 105.0,
        "candle_close": 111.0,
    }
    candle[field] = value

    with pytest.raises(TypeError, match=f"{field} must be a real number"):
        BreakerBlockEngine().evaluate_retest(
            bullish_breaker(),
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
def test_retest_rejects_non_finite_prices(
    field: str,
    value: float,
) -> None:
    candle = {
        "candle_high": 112.0,
        "candle_low": 105.0,
        "candle_close": 111.0,
    }
    candle[field] = value

    with pytest.raises(ValueError, match=f"{field} must be finite"):
        BreakerBlockEngine().evaluate_retest(
            bullish_breaker(),
            **candle,
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("candle_high", 0.0),
        ("candle_low", -1.0),
        ("candle_close", 0.0),
    ],
)
def test_retest_rejects_non_positive_prices(
    field: str,
    value: float,
) -> None:
    candle = {
        "candle_high": 112.0,
        "candle_low": 105.0,
        "candle_close": 111.0,
    }
    candle[field] = value

    with pytest.raises(
        ValueError,
        match=f"{field} must be greater than zero",
    ):
        BreakerBlockEngine().evaluate_retest(
            bullish_breaker(),
            **candle,
        )


def test_retest_rejects_high_below_low() -> None:
    with pytest.raises(
        ValueError,
        match="candle_high must be greater than or equal",
    ):
        BreakerBlockEngine().evaluate_retest(
            bullish_breaker(),
            candle_high=104.0,
            candle_low=105.0,
            candle_close=104.5,
        )


def test_retest_rejects_close_above_high() -> None:
    with pytest.raises(
        ValueError,
        match="candle_close cannot be above candle_high",
    ):
        BreakerBlockEngine().evaluate_retest(
            bullish_breaker(),
            candle_high=110.0,
            candle_low=100.0,
            candle_close=111.0,
        )


def test_retest_rejects_close_below_low() -> None:
    with pytest.raises(
        ValueError,
        match="candle_close cannot be below candle_low",
    ):
        BreakerBlockEngine().evaluate_retest(
            bullish_breaker(),
            candle_high=110.0,
            candle_low=100.0,
            candle_close=99.0,
        )


def test_retest_result_is_immutable() -> None:
    result = BreakerBlockEngine().evaluate_retest(
        bullish_breaker(),
        candle_high=112.0,
        candle_low=105.0,
        candle_close=111.0,
    )

    with pytest.raises(FrozenInstanceError):
        result.rejected = False  # type: ignore[misc]


def test_breaker_result_rejects_conflicting_direction() -> None:
    with pytest.raises(
        ValueError,
        match="exactly one active direction",
    ):
        BreakerBlock(
            bullish=True,
            bearish=True,
            zone_high=110.0,
            zone_low=100.0,
            confirmed=True,
            breakout_price=115.0,
        )


def test_breaker_result_rejects_direction_when_unconfirmed() -> None:
    with pytest.raises(
        ValueError,
        match="unconfirmed breaker cannot have an active direction",
    ):
        BreakerBlock(
            bullish=True,
            bearish=False,
            zone_high=110.0,
            zone_low=100.0,
            confirmed=False,
            breakout_price=None,
        )


def test_breaker_result_rejects_invalid_bullish_breakout_price() -> None:
    with pytest.raises(
        ValueError,
        match="bullish breakout_price must be above zone_high",
    ):
        BreakerBlock(
            bullish=True,
            bearish=False,
            zone_high=110.0,
            zone_low=100.0,
            confirmed=True,
            breakout_price=110.0,
        )


def test_retest_result_rejects_rejected_and_invalidated() -> None:
    with pytest.raises(
        ValueError,
        match="cannot be both rejected and invalidated",
    ):
        BreakerRetestResult(
            bullish=True,
            bearish=False,
            zone_high=110.0,
            zone_low=100.0,
            touched=True,
            rejected=True,
            invalidated=True,
            penetration_ratio=1.0,
        )