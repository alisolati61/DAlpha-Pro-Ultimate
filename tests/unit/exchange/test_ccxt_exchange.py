import pytest

ccxt = pytest.importorskip("ccxt.async_support")

from src.exchange.ccxt_exchange import CCXTExchange


def test_create():

    exchange = CCXTExchange(
        "binance",
    )

    assert exchange is not None


def test_type():

    exchange = CCXTExchange(
        "binance",
    )

    assert hasattr(
        exchange,
        "exchange",
    )