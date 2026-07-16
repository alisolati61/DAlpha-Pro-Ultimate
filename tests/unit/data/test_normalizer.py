from src.data.normalizer import MarketDataNormalizer


def test_binance_normalizer():

    normalizer = MarketDataNormalizer()

    data = normalizer.normalize_binance(
        {
            "symbol": "BTCUSDT",
            "price": "100000",
            "bid": "99990",
            "ask": "100010",
            "volume": "120",
            "timestamp": 1700000000,
        }
    )

    assert data.symbol == "BTCUSDT"
    assert data.price == 100000
    assert data.bid == 99990
    assert data.ask == 100010
    assert data.volume == 120


def test_bybit_normalizer():

    normalizer = MarketDataNormalizer()

    data = normalizer.normalize_bybit(
        {
            "symbol": "BTCUSDT",
            "lastPrice": "100000",
            "bidPrice": "99990",
            "askPrice": "100010",
            "volume24h": "500",
            "timestamp": 1700000000,
        }
    )

    assert data.symbol == "BTCUSDT"
    assert data.price == 100000
    assert data.volume == 500