from src.domain.order import Order
from src.drivers.paper_driver import PaperDriver


def test_place_order():

    driver = PaperDriver()

    order = Order(
        symbol="BTCUSDT",
        side="BUY",
        quantity=1,
        price=100000,
    )

    order_id = driver.place_order(order)

    assert isinstance(order_id, str)


def test_cancel():

    driver = PaperDriver()

    assert driver.cancel_order("1")


def test_status():

    driver = PaperDriver()

    assert driver.get_order_status("1") == "FILLED"


def test_health():

    driver = PaperDriver()

    assert driver.health_check()


def test_balance():

    driver = PaperDriver()

    balance = driver.get_balance()

    assert "USDT" in balance


def test_positions():

    driver = PaperDriver()

    positions = driver.get_positions()

    assert isinstance(positions, list)


def test_ticker():

    driver = PaperDriver()

    ticker = driver.get_ticker("BTCUSDT")

    assert ticker["symbol"] == "BTCUSDT"


def test_orderbook():

    driver = PaperDriver()

    orderbook = driver.get_orderbook("BTCUSDT")

    assert isinstance(orderbook, dict)


def test_ohlcv():

    driver = PaperDriver()

    candles = driver.get_ohlcv(
        "BTCUSDT",
        "1m",
    )

    assert isinstance(candles, list)