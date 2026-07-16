from src.data.orderbook_manager import OrderBookManager


def test_update():

    manager = OrderBookManager()

    manager.update(

        "BTCUSDT",

        bids=[(100000, 2), (99990, 1)],

        asks=[(100010, 3), (100020, 1)],

    )

    assert manager.exists("BTCUSDT")


def test_best_bid():

    manager = OrderBookManager()

    manager.update(

        "BTCUSDT",

        bids=[(100000, 2), (99990, 1)],

        asks=[(100010, 3)],

    )

    assert manager.best_bid("BTCUSDT") == 100000


def test_best_ask():

    manager = OrderBookManager()

    manager.update(

        "BTCUSDT",

        bids=[(100000, 2)],

        asks=[(100010, 3), (100020, 1)],

    )

    assert manager.best_ask("BTCUSDT") == 100010


def test_get():

    manager = OrderBookManager()

    manager.update(

        "BTCUSDT",

        bids=[(100000, 1)],

        asks=[(100010, 1)],

    )

    book = manager.get("BTCUSDT")

    assert book is not None

    assert len(book.bids) == 1

    assert len(book.asks) == 1