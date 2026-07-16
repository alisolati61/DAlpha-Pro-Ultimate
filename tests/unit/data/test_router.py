from datetime import datetime

from src.data.router import MarketDataRouter
from src.domain.market_data import MarketData


def test_publish():

    router = MarketDataRouter()

    received = []

    def handler(data: MarketData):
        received.append(data)

    router.subscribe(
        "BTCUSDT",
        handler,
    )

    router.publish(
        MarketData(
            symbol="BTCUSDT",
            price=100000,
            bid=99999,
            ask=100001,
            volume=100,
            timestamp=datetime.now(),
        )
    )

    assert len(received) == 1


def test_subscriber_count():

    router = MarketDataRouter()

    router.subscribe("BTCUSDT", lambda x: None)
    router.subscribe("BTCUSDT", lambda x: None)

    assert router.subscriber_count("BTCUSDT") == 2