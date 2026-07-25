"""Tests for validated execution-layer order construction."""

from fractions import Fraction
from math import inf, nan

import pytest

from src.domain.order import Order
from src.execution.order_manager import (
    OrderManager,
)


@pytest.fixture
def manager() -> OrderManager:
    return OrderManager()


def test_create_market_order(
    manager: OrderManager,
) -> None:
    order = manager.create_market_order(
        symbol="BTC/USDT",
        side="buy",
        quantity=1.5,
    )

    assert isinstance(order, Order)
    assert order.symbol == "BTC/USDT"
    assert order.side == "buy"
    assert order.order_type == "market"
    assert order.quantity == 1.5
    assert order.price is None


def test_create_limit_order(
    manager: OrderManager,
) -> None:
    order = manager.create_limit_order(
        symbol="BTC/USDT",
        side="sell",
        quantity=2,
        price=50_000,
    )

    assert isinstance(order, Order)
    assert order.symbol == "BTC/USDT"
    assert order.side == "sell"
    assert order.order_type == "limit"
    assert order.quantity == 2.0
    assert order.price == 50_000.0


def test_created_numeric_fields_are_floats(
    manager: OrderManager,
) -> None:
    market = manager.create_market_order(
        symbol="BTCUSDT",
        side="buy",
        quantity=1,
    )
    limit = manager.create_limit_order(
        symbol="ETHUSDT",
        side="sell",
        quantity=2,
        price=2500,
    )

    assert type(market.quantity) is float
    assert type(limit.quantity) is float
    assert type(limit.price) is float


def test_market_order_has_no_limit_price(
    manager: OrderManager,
) -> None:
    order = manager.create_market_order(
        symbol="ETH/USDT",
        side="sell",
        quantity=2.5,
    )

    assert order.price is None


def test_limit_order_preserves_values(
    manager: OrderManager,
) -> None:
    order = manager.create_limit_order(
        symbol="ETH/USDT",
        side="sell",
        quantity=2.5,
        price=2_500.75,
    )

    assert order.quantity == 2.5
    assert order.price == 2_500.75


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (
            "BUY",
            "buy",
        ),
        (
            "Buy",
            "buy",
        ),
        (
            " bUy ",
            "buy",
        ),
        (
            "SELL",
            "sell",
        ),
        (
            "Sell",
            "sell",
        ),
        (
            " sElL ",
            "sell",
        ),
    ],
)
def test_side_is_normalized(
    manager: OrderManager,
    source: str,
    expected: str,
) -> None:
    order = manager.create_market_order(
        symbol="BTCUSDT",
        side=source,
        quantity=1,
    )

    assert order.side == expected


@pytest.mark.parametrize(
    "factory_name",
    [
        "market",
        "limit",
    ],
)
def test_symbol_whitespace_is_stripped(
    manager: OrderManager,
    factory_name: str,
) -> None:
    if factory_name == "market":
        order = manager.create_market_order(
            symbol="  BTC/USDT  ",
            side="buy",
            quantity=1,
        )
    else:
        order = manager.create_limit_order(
            symbol="  BTC/USDT  ",
            side="buy",
            quantity=1,
            price=100,
        )

    assert order.symbol == "BTC/USDT"


def test_generic_market_order(
    manager: OrderManager,
) -> None:
    order = manager.create_order(
        symbol="BTCUSDT",
        side="BUY",
        order_type=" MARKET ",
        quantity=1,
    )

    assert order.order_type == "market"
    assert order.price is None


def test_generic_limit_order(
    manager: OrderManager,
) -> None:
    order = manager.create_order(
        symbol="BTCUSDT",
        side="SELL",
        order_type=" LIMIT ",
        quantity=1,
        price=100,
    )

    assert order.order_type == "limit"
    assert order.price == 100.0


def test_market_order_rejects_price(
    manager: OrderManager,
) -> None:
    with pytest.raises(
        ValueError,
        match="market order price must be None",
    ):
        manager.create_order(
            symbol="BTCUSDT",
            side="buy",
            order_type="market",
            quantity=1,
            price=100,
        )


def test_limit_order_requires_price(
    manager: OrderManager,
) -> None:
    with pytest.raises(
        ValueError,
        match="limit order price is required",
    ):
        manager.create_order(
            symbol="BTCUSDT",
            side="buy",
            order_type="limit",
            quantity=1,
        )


@pytest.mark.parametrize(
    "order_type",
    [
        "",
        " ",
        "stop",
        "stop_limit",
        "maker",
        "buy",
    ],
)
def test_invalid_order_type(
    manager: OrderManager,
    order_type: str,
) -> None:
    with pytest.raises(
        ValueError,
        match=(
            "order_type must be 'market' "
            "or 'limit'"
        ),
    ):
        manager.create_order(
            symbol="BTCUSDT",
            side="buy",
            order_type=order_type,
            quantity=1,
        )


@pytest.mark.parametrize(
    "order_type",
    [
        None,
        1,
        True,
        [],
        object(),
    ],
)
def test_invalid_order_type_type(
    manager: OrderManager,
    order_type: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="order_type must be a string",
    ):
        manager.create_order(
            symbol="BTCUSDT",
            side="buy",
            order_type=order_type,  # type: ignore[arg-type]
            quantity=1,
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
@pytest.mark.parametrize(
    "factory_name",
    [
        "market",
        "limit",
    ],
)
def test_empty_symbol_is_rejected(
    manager: OrderManager,
    symbol: str,
    factory_name: str,
) -> None:
    with pytest.raises(
        ValueError,
        match="symbol cannot be empty",
    ):
        if factory_name == "market":
            manager.create_market_order(
                symbol=symbol,
                side="buy",
                quantity=1,
            )
        else:
            manager.create_limit_order(
                symbol=symbol,
                side="buy",
                quantity=1,
                price=100,
            )


@pytest.mark.parametrize(
    "symbol",
    [
        None,
        123,
        True,
        [],
        {},
        object(),
    ],
)
def test_invalid_symbol_type(
    manager: OrderManager,
    symbol: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="symbol must be a string",
    ):
        manager.create_market_order(
            symbol=symbol,  # type: ignore[arg-type]
            side="buy",
            quantity=1,
        )


def test_symbol_length_is_bounded(
    manager: OrderManager,
) -> None:
    with pytest.raises(
        ValueError,
        match=(
            "symbol must not exceed "
            "100 characters"
        ),
    ):
        manager.create_market_order(
            symbol="x" * 101,
            side="buy",
            quantity=1,
        )


def test_maximum_symbol_length_is_accepted(
    manager: OrderManager,
) -> None:
    order = manager.create_market_order(
        symbol="x" * 100,
        side="buy",
        quantity=1,
    )

    assert len(order.symbol) == 100


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
@pytest.mark.parametrize(
    "factory_name",
    [
        "market",
        "limit",
    ],
)
def test_invalid_side(
    manager: OrderManager,
    side: str,
    factory_name: str,
) -> None:
    with pytest.raises(
        ValueError,
        match="side must be 'buy' or 'sell'",
    ):
        if factory_name == "market":
            manager.create_market_order(
                symbol="BTCUSDT",
                side=side,
                quantity=1,
            )
        else:
            manager.create_limit_order(
                symbol="BTCUSDT",
                side=side,
                quantity=1,
                price=100,
            )


@pytest.mark.parametrize(
    "side",
    [
        None,
        123,
        True,
        [],
        {},
        object(),
    ],
)
def test_invalid_side_type(
    manager: OrderManager,
    side: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="side must be a string",
    ):
        manager.create_market_order(
            symbol="BTCUSDT",
            side=side,  # type: ignore[arg-type]
            quantity=1,
        )


@pytest.mark.parametrize(
    "quantity",
    [
        0,
        -1,
        -0.1,
    ],
)
@pytest.mark.parametrize(
    "factory_name",
    [
        "market",
        "limit",
    ],
)
def test_non_positive_quantity(
    manager: OrderManager,
    quantity: float,
    factory_name: str,
) -> None:
    with pytest.raises(
        ValueError,
        match=(
            "quantity must be greater "
            "than zero"
        ),
    ):
        if factory_name == "market":
            manager.create_market_order(
                symbol="BTCUSDT",
                side="buy",
                quantity=quantity,
            )
        else:
            manager.create_limit_order(
                symbol="BTCUSDT",
                side="buy",
                quantity=quantity,
                price=100,
            )


@pytest.mark.parametrize(
    "quantity",
    [
        nan,
        inf,
        -inf,
    ],
)
def test_non_finite_quantity(
    manager: OrderManager,
    quantity: float,
) -> None:
    with pytest.raises(
        ValueError,
        match="quantity must be finite",
    ):
        manager.create_market_order(
            symbol="BTCUSDT",
            side="buy",
            quantity=quantity,
        )


@pytest.mark.parametrize(
    "quantity",
    [
        True,
        False,
        None,
        "1",
        [],
        {},
        object(),
    ],
)
def test_invalid_quantity_type(
    manager: OrderManager,
    quantity: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="quantity must be a number",
    ):
        manager.create_market_order(
            symbol="BTCUSDT",
            side="buy",
            quantity=quantity,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "price",
    [
        0,
        -1,
        -0.1,
    ],
)
def test_non_positive_price(
    manager: OrderManager,
    price: float,
) -> None:
    with pytest.raises(
        ValueError,
        match="price must be greater than zero",
    ):
        manager.create_limit_order(
            symbol="BTCUSDT",
            side="buy",
            quantity=1,
            price=price,
        )


@pytest.mark.parametrize(
    "price",
    [
        nan,
        inf,
        -inf,
    ],
)
def test_non_finite_price(
    manager: OrderManager,
    price: float,
) -> None:
    with pytest.raises(
        ValueError,
        match="price must be finite",
    ):
        manager.create_limit_order(
            symbol="BTCUSDT",
            side="buy",
            quantity=1,
            price=price,
        )


@pytest.mark.parametrize(
    "price",
    [
        True,
        False,
        None,
        "100",
        [],
        {},
        object(),
    ],
)
def test_invalid_price_type(
    manager: OrderManager,
    price: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="price must be a number",
    ):
        manager.create_limit_order(
            symbol="BTCUSDT",
            side="buy",
            quantity=1,
            price=price,  # type: ignore[arg-type]
        )


def test_fraction_quantity_is_supported(
    manager: OrderManager,
) -> None:
    order = manager.create_market_order(
        symbol="BTCUSDT",
        side="buy",
        quantity=Fraction(1, 2),
    )

    assert order.quantity == 0.5


def test_fraction_price_is_supported(
    manager: OrderManager,
) -> None:
    order = manager.create_limit_order(
        symbol="BTCUSDT",
        side="buy",
        quantity=1,
        price=Fraction(201, 2),
    )

    assert order.price == 100.5


def test_orders_are_independent_instances(
    manager: OrderManager,
) -> None:
    first = manager.create_market_order(
        symbol="BTCUSDT",
        side="buy",
        quantity=1,
    )
    second = manager.create_market_order(
        symbol="ETHUSDT",
        side="sell",
        quantity=2,
    )

    assert first is not second

    first.symbol = "CHANGED"

    assert second.symbol == "ETHUSDT"


def test_market_and_limit_orders_are_independent(
    manager: OrderManager,
) -> None:
    market = manager.create_market_order(
        symbol="BTCUSDT",
        side="buy",
        quantity=1,
    )
    limit = manager.create_limit_order(
        symbol="BTCUSDT",
        side="buy",
        quantity=1,
        price=100,
    )

    assert market is not limit
    assert market.price is None
    assert limit.price == 100.0


def test_validation_order_starts_with_symbol(
    manager: OrderManager,
) -> None:
    with pytest.raises(
        ValueError,
        match="symbol cannot be empty",
    ):
        manager.create_limit_order(
            symbol=" ",
            side="invalid",
            quantity=-1,
            price=-1,
        )


def test_validation_order_checks_side_before_quantity(
    manager: OrderManager,
) -> None:
    with pytest.raises(
        ValueError,
        match="side must be 'buy' or 'sell'",
    ):
        manager.create_market_order(
            symbol="BTCUSDT",
            side="invalid",
            quantity=-1,
        )


def test_validation_order_checks_quantity_before_price(
    manager: OrderManager,
) -> None:
    with pytest.raises(
        ValueError,
        match=(
            "quantity must be greater "
            "than zero"
        ),
    ):
        manager.create_limit_order(
            symbol="BTCUSDT",
            side="buy",
            quantity=-1,
            price=-1,
        )