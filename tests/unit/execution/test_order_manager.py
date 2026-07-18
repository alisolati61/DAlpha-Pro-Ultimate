from __future__ import annotations

import math

import pytest

from src.domain.order import Order
from src.execution.order_manager import OrderManager


@pytest.fixture
def manager() -> OrderManager:

    return OrderManager()


def test_create_market_order_returns_order(
    manager,
):

    order = manager.create_market_order(
        symbol="BTC/USDT",
        side="buy",
        quantity=1.5,
    )

    assert isinstance(
        order,
        Order,
    )


def test_create_market_order_symbol_is_preserved(
    manager,
):

    order = manager.create_market_order(
        symbol="BTC/USDT",
        side="buy",
        quantity=1.5,
    )

    assert order.symbol == "BTC/USDT"


def test_create_market_order_side_is_normalized(
    manager,
):

    order = manager.create_market_order(
        symbol="BTC/USDT",
        side="BUY",
        quantity=1.5,
    )

    assert order.side == "buy"


def test_create_market_order_type_is_market(
    manager,
):

    order = manager.create_market_order(
        symbol="BTC/USDT",
        side="buy",
        quantity=1.5,
    )

    assert order.order_type == "market"


def test_create_market_order_quantity_is_float(
    manager,
):

    order = manager.create_market_order(
        symbol="BTC/USDT",
        side="buy",
        quantity=1,
    )

    assert isinstance(
        order.quantity,
        float,
    )

    assert order.quantity == 1.0


def test_create_market_order_price_is_none(
    manager,
):

    order = manager.create_market_order(
        symbol="BTC/USDT",
        side="buy",
        quantity=1.5,
    )

    assert order.price is None


def test_create_limit_order_returns_order(
    manager,
):

    order = manager.create_limit_order(
        symbol="BTC/USDT",
        side="sell",
        quantity=2.0,
        price=50_000,
    )

    assert isinstance(
        order,
        Order,
    )


def test_create_limit_order_type_is_limit(
    manager,
):

    order = manager.create_limit_order(
        symbol="BTC/USDT",
        side="sell",
        quantity=2.0,
        price=50_000,
    )

    assert order.order_type == "limit"


def test_create_limit_order_price_is_float(
    manager,
):

    order = manager.create_limit_order(
        symbol="BTC/USDT",
        side="sell",
        quantity=2.0,
        price=50_000,
    )

    assert isinstance(
        order.price,
        float,
    )

    assert order.price == 50_000.0


@pytest.mark.parametrize(
    "symbol",
    [
        "",
        " ",
        "\t",
        "\n",
    ],
)
def test_market_order_rejects_empty_symbol(
    manager,
    symbol,
):

    with pytest.raises(
        ValueError,
        match="symbol cannot be empty",
    ):

        manager.create_market_order(
            symbol=symbol,
            side="buy",
            quantity=1.0,
        )


@pytest.mark.parametrize(
    "symbol",
    [
        "",
        " ",
        "\t",
        "\n",
    ],
)
def test_limit_order_rejects_empty_symbol(
    manager,
    symbol,
):

    with pytest.raises(
        ValueError,
        match="symbol cannot be empty",
    ):

        manager.create_limit_order(
            symbol=symbol,
            side="buy",
            quantity=1.0,
            price=100.0,
        )


@pytest.mark.parametrize(
    "symbol",
    [
        None,
        123,
        True,
        [],
    ],
)
def test_market_order_rejects_invalid_symbol_type(
    manager,
    symbol,
):

    with pytest.raises(
        TypeError,
        match="symbol must be a string",
    ):

        manager.create_market_order(
            symbol=symbol,
            side="buy",
            quantity=1.0,
        )


@pytest.mark.parametrize(
    "side",
    [
        "",
        " ",
        "hold",
        "buy_sell",
        "long",
        "short",
    ],
)
def test_market_order_rejects_invalid_side(
    manager,
    side,
):

    with pytest.raises(
        ValueError,
        match="side must be 'buy' or 'sell'",
    ):

        manager.create_market_order(
            symbol="BTC/USDT",
            side=side,
            quantity=1.0,
        )


@pytest.mark.parametrize(
    "side",
    [
        "",
        " ",
        "hold",
        "buy_sell",
        "long",
        "short",
    ],
)
def test_limit_order_rejects_invalid_side(
    manager,
    side,
):

    with pytest.raises(
        ValueError,
        match="side must be 'buy' or 'sell'",
    ):

        manager.create_limit_order(
            symbol="BTC/USDT",
            side=side,
            quantity=1.0,
            price=100.0,
        )


@pytest.mark.parametrize(
    "side",
    [
        None,
        123,
        True,
        [],
    ],
)
def test_market_order_rejects_invalid_side_type(
    manager,
    side,
):

    with pytest.raises(
        TypeError,
        match="side must be a string",
    ):

        manager.create_market_order(
            symbol="BTC/USDT",
            side=side,
            quantity=1.0,
        )


@pytest.mark.parametrize(
    "quantity",
    [
        0,
        -1,
        -0.1,
    ],
)
def test_market_order_rejects_non_positive_quantity(
    manager,
    quantity,
):

    with pytest.raises(
        ValueError,
        match="quantity must be greater than zero",
    ):

        manager.create_market_order(
            symbol="BTC/USDT",
            side="buy",
            quantity=quantity,
        )


@pytest.mark.parametrize(
    "quantity",
    [
        0,
        -1,
        -0.1,
    ],
)
def test_limit_order_rejects_non_positive_quantity(
    manager,
    quantity,
):

    with pytest.raises(
        ValueError,
        match="quantity must be greater than zero",
    ):

        manager.create_limit_order(
            symbol="BTC/USDT",
            side="buy",
            quantity=quantity,
            price=100.0,
        )


@pytest.mark.parametrize(
    "quantity",
    [
        None,
        "1.0",
        [],
        {},
    ],
)
def test_market_order_rejects_invalid_quantity_type(
    manager,
    quantity,
):

    with pytest.raises(
        TypeError,
        match="quantity must be a number",
    ):

        manager.create_market_order(
            symbol="BTC/USDT",
            side="buy",
            quantity=quantity,
        )


@pytest.mark.parametrize(
    "quantity",
    [
        True,
        False,
    ],
)
def test_market_order_rejects_boolean_quantity(
    manager,
    quantity,
):

    with pytest.raises(
        TypeError,
        match="quantity must be a number",
    ):

        manager.create_market_order(
            symbol="BTC/USDT",
            side="buy",
            quantity=quantity,
        )


@pytest.mark.parametrize(
    "quantity",
    [
        math.inf,
        -math.inf,
        math.nan,
    ],
)
def test_market_order_rejects_non_finite_quantity(
    manager,
    quantity,
):

    with pytest.raises(
        ValueError,
        match="quantity must be finite",
    ):

        manager.create_market_order(
            symbol="BTC/USDT",
            side="buy",
            quantity=quantity,
        )


@pytest.mark.parametrize(
    "price",
    [
        0,
        -1,
        -0.1,
    ],
)
def test_limit_order_rejects_non_positive_price(
    manager,
    price,
):

    with pytest.raises(
        ValueError,
        match="price must be greater than zero",
    ):

        manager.create_limit_order(
            symbol="BTC/USDT",
            side="buy",
            quantity=1.0,
            price=price,
        )


@pytest.mark.parametrize(
    "price",
    [
        None,
        "100",
        [],
        {},
    ],
)
def test_limit_order_rejects_invalid_price_type(
    manager,
    price,
):

    with pytest.raises(
        TypeError,
        match="price must be a number",
    ):

        manager.create_limit_order(
            symbol="BTC/USDT",
            side="buy",
            quantity=1.0,
            price=price,
        )


@pytest.mark.parametrize(
    "price",
    [
        True,
        False,
    ],
)
def test_limit_order_rejects_boolean_price(
    manager,
    price,
):

    with pytest.raises(
        TypeError,
        match="price must be a number",
    ):

        manager.create_limit_order(
            symbol="BTC/USDT",
            side="buy",
            quantity=1.0,
            price=price,
        )


@pytest.mark.parametrize(
    "price",
    [
        math.inf,
        -math.inf,
        math.nan,
    ],
)
def test_limit_order_rejects_non_finite_price(
    manager,
    price,
):

    with pytest.raises(
        ValueError,
        match="price must be finite",
    ):

        manager.create_limit_order(
            symbol="BTC/USDT",
            side="buy",
            quantity=1.0,
            price=price,
        )


def test_market_order_strips_symbol_whitespace(
    manager,
):

    order = manager.create_market_order(
        symbol="  BTC/USDT  ",
        side="buy",
        quantity=1.0,
    )

    assert order.symbol == "BTC/USDT"


def test_market_order_strips_side_whitespace(
    manager,
):

    order = manager.create_market_order(
        symbol="BTC/USDT",
        side="  BUY  ",
        quantity=1.0,
    )

    assert order.side == "buy"


def test_limit_order_strips_symbol_whitespace(
    manager,
):

    order = manager.create_limit_order(
        symbol="  BTC/USDT  ",
        side="sell",
        quantity=1.0,
        price=100.0,
    )

    assert order.symbol == "BTC/USDT"


def test_limit_order_strips_side_whitespace(
    manager,
):

    order = manager.create_limit_order(
        symbol="BTC/USDT",
        side="  SELL  ",
        quantity=1.0,
        price=100.0,
    )

    assert order.side == "sell"


@pytest.mark.parametrize(
    "side",
    [
        "BUY",
        "Buy",
        " bUy ",
    ],
)
def test_market_order_accepts_case_insensitive_buy(
    manager,
    side,
):

    order = manager.create_market_order(
        symbol="BTC/USDT",
        side=side,
        quantity=1.0,
    )

    assert order.side == "buy"


@pytest.mark.parametrize(
    "side",
    [
        "SELL",
        "Sell",
        " sElL ",
    ],
)
def test_limit_order_accepts_case_insensitive_sell(
    manager,
    side,
):

    order = manager.create_limit_order(
        symbol="BTC/USDT",
        side=side,
        quantity=1.0,
        price=100.0,
    )

    assert order.side == "sell"


def test_market_order_accepts_integer_quantity(
    manager,
):

    order = manager.create_market_order(
        symbol="BTC/USDT",
        side="buy",
        quantity=5,
    )

    assert order.quantity == 5.0

    assert isinstance(
        order.quantity,
        float,
    )


def test_limit_order_accepts_integer_quantity(
    manager,
):

    order = manager.create_limit_order(
        symbol="BTC/USDT",
        side="buy",
        quantity=5,
        price=100,
    )

    assert order.quantity == 5.0

    assert isinstance(
        order.quantity,
        float,
    )


def test_limit_order_accepts_integer_price(
    manager,
):

    order = manager.create_limit_order(
        symbol="BTC/USDT",
        side="buy",
        quantity=1.0,
        price=100,
    )

    assert order.price == 100.0

    assert isinstance(
        order.price,
        float,
    )


def test_market_order_has_no_limit_price(
    manager,
):

    order = manager.create_market_order(
        symbol="ETH/USDT",
        side="sell",
        quantity=2.5,
    )

    assert order.price is None


def test_limit_order_preserves_quantity_and_price(
    manager,
):

    order = manager.create_limit_order(
        symbol="ETH/USDT",
        side="sell",
        quantity=2.5,
        price=2_500.75,
    )

    assert order.quantity == 2.5

    assert order.price == 2_500.75


def test_market_order_creates_independent_order_instances(
    manager,
):

    first = manager.create_market_order(
        symbol="BTC/USDT",
        side="buy",
        quantity=1.0,
    )

    second = manager.create_market_order(
        symbol="ETH/USDT",
        side="sell",
        quantity=2.0,
    )

    assert first is not second

    assert first.symbol == "BTC/USDT"

    assert second.symbol == "ETH/USDT"


def test_limit_order_creates_independent_order_instances(
    manager,
):

    first = manager.create_limit_order(
        symbol="BTC/USDT",
        side="buy",
        quantity=1.0,
        price=100.0,
    )

    second = manager.create_limit_order(
        symbol="ETH/USDT",
        side="sell",
        quantity=2.0,
        price=200.0,
    )

    assert first is not second

    assert first.symbol == "BTC/USDT"

    assert second.symbol == "ETH/USDT"