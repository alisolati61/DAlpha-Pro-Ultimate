import math

import pytest

from src.analysis.smart_money.liquidity import (
    LiquidityEngine,
    LiquidityZone,
)


@pytest.fixture
def engine() -> LiquidityEngine:
    return LiquidityEngine()


def test_detects_buy_side_liquidity(
    engine: LiquidityEngine,
) -> None:
    result = engine.detect(
        equal_high=True,
        equal_low=False,
        high_price=118_500,
        low_price=116_800,
    )

    assert result == LiquidityZone(
        buy_side=True,
        sell_side=False,
        price=118_500.0,
        valid=True,
    )


def test_detects_sell_side_liquidity(
    engine: LiquidityEngine,
) -> None:
    result = engine.detect(
        equal_high=False,
        equal_low=True,
        high_price=118_500,
        low_price=116_800,
    )

    assert result == LiquidityZone(
        buy_side=False,
        sell_side=True,
        price=116_800.0,
        valid=True,
    )


def test_returns_invalid_zone_when_no_liquidity_exists(
    engine: LiquidityEngine,
) -> None:
    result = engine.detect(
        equal_high=False,
        equal_low=False,
        high_price=118_500,
        low_price=116_800,
    )

    assert result == LiquidityZone(
        buy_side=False,
        sell_side=False,
        price=None,
        valid=False,
    )


def test_accepts_float_prices(
    engine: LiquidityEngine,
) -> None:
    result = engine.detect(
        equal_high=True,
        equal_low=False,
        high_price=118_500.75,
        low_price=116_800.25,
    )

    assert result.buy_side is True
    assert result.sell_side is False
    assert result.price == pytest.approx(118_500.75)
    assert result.valid is True


def test_rejects_simultaneous_equal_high_and_low(
    engine: LiquidityEngine,
) -> None:
    with pytest.raises(
        ValueError,
        match="equal_high and equal_low cannot both be True",
    ):
        engine.detect(
            equal_high=True,
            equal_low=True,
            high_price=118_500,
            low_price=116_800,
        )


@pytest.mark.parametrize(
    "invalid_flag",
    [
        1,
        0,
        "True",
        None,
        [],
    ],
)
def test_rejects_invalid_equal_high_flag(
    engine: LiquidityEngine,
    invalid_flag: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="equal_high must be a boolean",
    ):
        engine.detect(
            equal_high=invalid_flag,  # type: ignore[arg-type]
            equal_low=False,
            high_price=118_500,
            low_price=116_800,
        )


@pytest.mark.parametrize(
    "invalid_flag",
    [
        1,
        0,
        "False",
        None,
        {},
    ],
)
def test_rejects_invalid_equal_low_flag(
    engine: LiquidityEngine,
    invalid_flag: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="equal_low must be a boolean",
    ):
        engine.detect(
            equal_high=False,
            equal_low=invalid_flag,  # type: ignore[arg-type]
            high_price=118_500,
            low_price=116_800,
        )


@pytest.mark.parametrize(
    "invalid_price",
    [
        0,
        -1,
        -100.5,
    ],
)
def test_rejects_non_positive_high_price(
    engine: LiquidityEngine,
    invalid_price: float,
) -> None:
    with pytest.raises(
        ValueError,
        match="high_price must be greater than zero",
    ):
        engine.detect(
            equal_high=True,
            equal_low=False,
            high_price=invalid_price,
            low_price=116_800,
        )


@pytest.mark.parametrize(
    "invalid_price",
    [
        math.nan,
        math.inf,
        -math.inf,
    ],
)
def test_rejects_non_finite_low_price(
    engine: LiquidityEngine,
    invalid_price: float,
) -> None:
    with pytest.raises(
        ValueError,
        match="low_price must be finite",
    ):
        engine.detect(
            equal_high=False,
            equal_low=True,
            high_price=118_500,
            low_price=invalid_price,
        )


@pytest.mark.parametrize(
    "invalid_price",
    [
        "118500",
        None,
        True,
        False,
    ],
)
def test_rejects_non_numeric_high_price(
    engine: LiquidityEngine,
    invalid_price: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="high_price must be a number",
    ):
        engine.detect(
            equal_high=True,
            equal_low=False,
            high_price=invalid_price,  # type: ignore[arg-type]
            low_price=116_800,
        )


def test_rejects_high_price_below_low_price(
    engine: LiquidityEngine,
) -> None:
    with pytest.raises(
        ValueError,
        match="high_price must be greater than low_price",
    ):
        engine.detect(
            equal_high=True,
            equal_low=False,
            high_price=116_000,
            low_price=118_000,
        )


def test_rejects_equal_high_and_low_prices(
    engine: LiquidityEngine,
) -> None:
    with pytest.raises(
        ValueError,
        match="high_price must be greater than low_price",
    ):
        engine.detect(
            equal_high=False,
            equal_low=True,
            high_price=118_000,
            low_price=118_000,
        )


def test_liquidity_zone_is_immutable() -> None:
    zone = LiquidityZone(
        buy_side=True,
        sell_side=False,
        price=118_500.0,
        valid=True,
    )

    with pytest.raises(AttributeError):
        zone.price = 120_000.0  # type: ignore[misc]