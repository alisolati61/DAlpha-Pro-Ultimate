from src.data.orderbook_manager import (
    OrderBook,
    OrderBookManager,
)


def sample():

    bids = [

        (100, 2),

        (99, 5),

        (98, 8),

    ]

    asks = [

        (101, 3),

        (102, 4),

        (103, 6),

    ]

    return bids, asks


def test_update():

    manager = OrderBookManager()

    bids, asks = sample()

    manager.update(
        "BTCUSDT",
        bids,
        asks,
    )

    assert isinstance(
        manager.get("BTCUSDT"),
        OrderBook,
    )


def test_best_bid():

    manager = OrderBookManager()

    bids, asks = sample()

    manager.update(
        "BTCUSDT",
        bids,
        asks,
    )

    assert manager.best_bid("BTCUSDT") == (100.0, 2.0)


def test_best_ask():

    manager = OrderBookManager()

    bids, asks = sample()

    manager.update(
        "BTCUSDT",
        bids,
        asks,
    )

    assert manager.best_ask("BTCUSDT") == (101.0, 3.0)


def test_clear():

    manager = OrderBookManager()

    bids, asks = sample()

    manager.update(
        "BTCUSDT",
        bids,
        asks,
    )

    manager.clear()

    assert manager.get("BTCUSDT") is None


def test_empty():

    manager = OrderBookManager()

    assert manager.best_bid("BTCUSDT") is None

    assert manager.best_ask("BTCUSDT") is None


def test_types():

    manager = OrderBookManager()

    bids, asks = sample()

    manager.update(
        "BTCUSDT",
        bids,
        asks,
    )

    book = manager.get("BTCUSDT")

    assert isinstance(book.bids, list)

    assert isinstance(book.asks, list)