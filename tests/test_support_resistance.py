import math

import pytest

from src.analysis.technical.support_resistance import (
    SupportResistance,
    SupportResistanceAnalyzer,
)
from src.market.market_data import MarketData


def create_market(
    last_price: float = 100.0,
) -> MarketData:
    return MarketData(
        symbol="BTC/USDT",
        last_price=last_price,
        bid=last_price - 0.05,
        ask=last_price + 0.05,
        volume=1_000_000,
    )


def test_calculate_support_and_resistance() -> None:
    market = create_market(last_price=100.0)

    levels = SupportResistanceAnalyzer.calculate(
        market,
        distance_percent=2.0,
    )

    assert isinstance(levels, SupportResistance)
    assert levels.support == pytest.approx(98.0)
    assert levels.resistance == pytest.approx(102.0)


def test_calculate_with_zero_distance() -> None:
    market = create_market(last_price=100.0)

    levels = SupportResistanceAnalyzer.calculate(
        market,
        distance_percent=0.0,
    )

    assert levels.support == pytest.approx(100.0)
    assert levels.resistance == pytest.approx(100.0)


def test_near_support_returns_true() -> None:
    market = create_market(last_price=98.2)

    levels = SupportResistance(
        support=98.0,
        resistance=102.0,
    )

    assert SupportResistanceAnalyzer.near_support(
        market,
        levels,
        tolerance_percent=0.5,
    )


def test_near_support_returns_false() -> None:
    market = create_market(last_price=100.0)

    levels = SupportResistance(
        support=98.0,
        resistance=102.0,
    )

    assert not SupportResistanceAnalyzer.near_support(
        market,
        levels,
        tolerance_percent=0.5,
    )


def test_near_resistance_returns_true() -> None:
    market = create_market(last_price=101.8)

    levels = SupportResistance(
        support=98.0,
        resistance=102.0,
    )

    assert SupportResistanceAnalyzer.near_resistance(
        market,
        levels,
        tolerance_percent=0.5,
    )


def test_near_resistance_returns_false() -> None:
    market = create_market(last_price=100.0)

    levels = SupportResistance(
        support=98.0,
        resistance=102.0,
    )

    assert not SupportResistanceAnalyzer.near_resistance(
        market,
        levels,
        tolerance_percent=0.5,
    )


def test_rejects_negative_distance() -> None:
    market = create_market()

    with pytest.raises(
        ValueError,
        match="distance_percent must not be negative",
    ):
        SupportResistanceAnalyzer.calculate(
            market,
            distance_percent=-2.0,
        )


def test_rejects_negative_tolerance() -> None:
    market = create_market()
    levels = SupportResistanceAnalyzer.calculate(market)

    with pytest.raises(
        ValueError,
        match="tolerance_percent must not be negative",
    ):
        SupportResistanceAnalyzer.near_support(
            market,
            levels,
            tolerance_percent=-0.5,
        )


def test_rejects_non_numeric_distance() -> None:
    market = create_market()

    with pytest.raises(
        TypeError,
        match="distance_percent must be a number",
    ):
        SupportResistanceAnalyzer.calculate(
            market,
            distance_percent="2",  # type: ignore[arg-type]
        )


def test_rejects_boolean_distance() -> None:
    market = create_market()

    with pytest.raises(
        TypeError,
        match="distance_percent must be a number",
    ):
        SupportResistanceAnalyzer.calculate(
            market,
            distance_percent=True,
        )


@pytest.mark.parametrize(
    "invalid_distance",
    [
        math.nan,
        math.inf,
        -math.inf,
    ],
)
def test_rejects_non_finite_distance(
    invalid_distance: float,
) -> None:
    market = create_market()

    with pytest.raises(
        ValueError,
        match="distance_percent must be finite",
    ):
        SupportResistanceAnalyzer.calculate(
            market,
            distance_percent=invalid_distance,
        )


def test_rejects_zero_market_price() -> None:
    market = create_market(last_price=0.0)

    with pytest.raises(
        ValueError,
        match="market.last_price must be greater than zero",
    ):
        SupportResistanceAnalyzer.calculate(market)


def test_rejects_negative_market_price() -> None:
    market = create_market(last_price=-100.0)

    with pytest.raises(
        ValueError,
        match="market.last_price must be greater than zero",
    ):
        SupportResistanceAnalyzer.calculate(market)


def test_rejects_invalid_market_object() -> None:
    with pytest.raises(
        TypeError,
        match="market must be a MarketData instance",
    ):
        SupportResistanceAnalyzer.calculate(
            None,  # type: ignore[arg-type]
        )


def test_near_support_rejects_invalid_levels() -> None:
    market = create_market()

    with pytest.raises(
        TypeError,
        match="levels must be a SupportResistance instance",
    ):
        SupportResistanceAnalyzer.near_support(
            market,
            None,  # type: ignore[arg-type]
        )


def test_near_resistance_rejects_invalid_levels() -> None:
    market = create_market()

    with pytest.raises(
        TypeError,
        match="levels must be a SupportResistance instance",
    ):
        SupportResistanceAnalyzer.near_resistance(
            market,
            None,  # type: ignore[arg-type]
        )