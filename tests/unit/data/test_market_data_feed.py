import pytest

from src.data.market_data_feed import MarketDataFeed


class DummyFeed(MarketDataFeed):

    def __init__(self):

        self.connected = False

    def connect(self):

        self.connected = True

    def disconnect(self):

        self.connected = False

    def is_connected(self):

        return self.connected

    def subscribe(
        self,
        symbol,
        timeframe,
    ):

        self.symbol = symbol

        self.timeframe = timeframe

    def unsubscribe(
        self,
        symbol,
        timeframe,
    ):

        self.symbol = None

        self.timeframe = None

    def latest(
        self,
        symbol,
        timeframe,
    ):

        return None


def test_connect():

    feed = DummyFeed()

    feed.connect()

    assert feed.is_connected()


def test_disconnect():

    feed = DummyFeed()

    feed.connect()

    feed.disconnect()

    assert not feed.is_connected()


def test_subscribe():

    feed = DummyFeed()

    feed.subscribe(
        "BTCUSDT",
        "1m",
    )

    assert feed.symbol == "BTCUSDT"


def test_unsubscribe():

    feed = DummyFeed()

    feed.subscribe(
        "BTCUSDT",
        "1m",
    )

    feed.unsubscribe(
        "BTCUSDT",
        "1m",
    )

    assert feed.symbol is None


def test_interface():

    with pytest.raises(TypeError):

        MarketDataFeed()