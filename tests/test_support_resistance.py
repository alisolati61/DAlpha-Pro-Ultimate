import pytest


def test_rejects_negative_distance() -> None:
    market = MarketData(
        symbol="BTC/USDT",
        last_price=100,
        bid=99.95,
        ask=100.05,
        volume=1_000_000,
    )

    with pytest.raises(ValueError, match="must not be negative"):
        SupportResistanceAnalyzer.calculate(
            market,
            distance_percent=-2,
        )


def test_rejects_negative_tolerance() -> None:
    market = MarketData(
        symbol="BTC/USDT",
        last_price=100,
        bid=99.95,
        ask=100.05,
        volume=1_000_000,
    )

    sr = SupportResistanceAnalyzer.calculate(market)

    with pytest.raises(ValueError, match="must not be negative"):
        SupportResistanceAnalyzer.near_support(
            market,
            sr,
            tolerance_percent=-0.5,
        )


def test_rejects_zero_market_price() -> None:
    market = MarketData(
        symbol="BTC/USDT",
        last_price=0,
        bid=0,
        ask=0,
        volume=1_000_000,
    )

    with pytest.raises(ValueError, match="greater than zero"):
        SupportResistanceAnalyzer.calculate(market)