from datetime import datetime

from src.core.types import (
    Price,
    Quantity,
    Symbol,
    Timestamp,
    JSON,
)


def test_basic_types():

    price: Price = 100.5

    qty: Quantity = 2.0

    symbol: Symbol = "BTCUSDT"

    ts: Timestamp = datetime.now()

    data: JSON = {"price": price}

    assert isinstance(price, float)

    assert isinstance(qty, float)

    assert isinstance(symbol, str)

    assert isinstance(ts, datetime)

    assert isinstance(data, dict)