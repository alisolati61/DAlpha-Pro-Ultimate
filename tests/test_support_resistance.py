from src.analysis.technical.support_resistance import (
    SupportResistanceAnalyzer,
)
from src.market.market_data import MarketData


def test_calculate():

    market = MarketData(
        symbol="BTC/USDT",
        last_price=100,
        bid=99.95,
        ask=100.05,
        volume=1000000,
    )

    sr = SupportResistanceAnalyzer.calculate(market)

    assert sr.support == 98

    assert sr.resistance == 102


def test_near_support():

    market = MarketData(
        symbol="BTC/USDT",
        last_price=98,
        bid=97.95,
        ask=98.05,
        volume=1000000,
    )

    sr = SupportResistanceAnalyzer(
    ).calculate(
        MarketData(
            symbol="BTC/USDT",
            last_price=100,
            bid=99.95,
            ask=100.05,
            volume=1000000,
        )
    )

    assert SupportResistanceAnalyzer.near_support(
        market,
        sr,
    )


def test_near_resistance():

    market = MarketData(
        symbol="BTC/USDT",
        last_price=102,
        bid=101.95,
        ask=102.05,
        volume=1000000,
    )

    sr = SupportResistanceAnalyzer.calculate(
        MarketData(
            symbol="BTC/USDT",
            last_price=100,
            bid=99.95,
            ask=100.05,
            volume=1000000,
        )
    )

    assert SupportResistanceAnalyzer.near_resistance(
        market,
        sr,
    )