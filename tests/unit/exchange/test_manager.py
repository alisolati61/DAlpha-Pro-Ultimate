import pytest

pytest.importorskip("ccxt.async_support")

from src.exchange.ccxt_exchange import CCXTExchange
from src.exchange.manager import ExchangeManager


def make():

    return CCXTExchange("binance")


def test_register():

    manager = ExchangeManager()

    manager.register(

        "binance",

        make(),

    )

    assert manager.exists("binance")


def test_get():

    manager = ExchangeManager()

    exchange = make()

    manager.register(

        "binance",

        exchange,

    )

    assert manager.get("binance") is exchange


def test_remove():

    manager = ExchangeManager()

    manager.register(

        "binance",

        make(),

    )

    manager.remove("binance")

    assert not manager.exists("binance")


def test_names():

    manager = ExchangeManager()

    manager.register(

        "binance",

        make(),

    )

    assert "binance" in manager.names()


def test_multiple():

    manager = ExchangeManager()

    manager.register(

        "binance",

        make(),

    )

    manager.register(

        "bybit",

        CCXTExchange("bybit"),

    )

    assert len(manager.names()) == 2