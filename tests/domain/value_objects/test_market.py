import pytest

from src.domain.value_objects import Market
from src.domain.value_objects import Symbol


def test_create_market():

    market = Market(
        base_asset="btc",
        quote_asset="usdt",
        symbol=Symbol("BTCUSDT"),
    )

    assert market.base_asset == "BTC"
    assert market.quote_asset == "USDT"
    assert market.symbol.value == "BTCUSDT"


def test_same_assets():

    with pytest.raises(ValueError):

        Market(
            base_asset="BTC",
            quote_asset="BTC",
            symbol=Symbol("BTCBTC"),
        )


def test_empty_base():

    with pytest.raises(ValueError):

        Market(
            base_asset="",
            quote_asset="USDT",
            symbol=Symbol("BTCUSDT"),
        )


def test_empty_quote():

    with pytest.raises(ValueError):

        Market(
            base_asset="BTC",
            quote_asset="",
            symbol=Symbol("BTCUSDT"),
        )