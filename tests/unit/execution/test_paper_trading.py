from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.execution.paper_trading import (
    PaperTrade,
    PaperTradingEngine,
)


@pytest.fixture
def engine() -> PaperTradingEngine:

    return PaperTradingEngine()


def test_execute_returns_paper_trade(
    engine,
):

    trade = engine.execute(
        symbol="BTC/USDT",
        side="buy",
        quantity=1.0,
        price=100.0,
    )

    assert isinstance(
        trade,
        PaperTrade,
    )


def test_execute_stores_trade(
    engine,
):

    trade = engine.execute(
        symbol="BTC/USDT",
        side="buy",
        quantity=1.0,
        price=100.0,
    )

    assert trade in engine.history()


def test_trade_symbol_is_preserved(
    engine,
):

    trade = engine.execute(
        symbol="BTC/USDT",
        side="buy",
        quantity=1.0,
        price=100.0,
    )

    assert trade.symbol == "BTC/USDT"


@pytest.mark.parametrize(
    "side, expected",
    [
        ("buy", "buy"),
        ("BUY", "buy"),
        (" Buy ", "buy"),
        ("sell", "sell"),
        ("SELL", "sell"),
        (" Sell ", "sell"),
    ],
)
def test_side_is_normalized(
    engine,
    side,
    expected,
):

    trade = engine.execute(
        symbol="BTC/USDT",
        side=side,
        quantity=1.0,
        price=100.0,
    )

    assert trade.side == expected


def test_quantity_is_float(
    engine,
):

    trade = engine.execute(
        symbol="BTC/USDT",
        side="buy",
        quantity=1,
        price=100.0,
    )

    assert isinstance(
        trade.quantity,
        float,
    )

    assert trade.quantity == 1.0


def test_price_is_float(
    engine,
):

    trade = engine.execute(
        symbol="BTC/USDT",
        side="buy",
        quantity=1.0,
        price=100,
    )

    assert isinstance(
        trade.entry_price,
        float,
    )

    assert trade.entry_price == 100.0


def test_timestamp_is_utc_aware(
    engine,
):

    trade = engine.execute(
        symbol="BTC/USDT",
        side="buy",
        quantity=1.0,
        price=100.0,
    )

    assert isinstance(
        trade.timestamp,
        datetime,
    )

    assert trade.timestamp.tzinfo == UTC


def test_symbol_whitespace_is_stripped(
    engine,
):

    trade = engine.execute(
        symbol="  BTC/USDT  ",
        side="buy",
        quantity=1.0,
        price=100.0,
    )

    assert trade.symbol == "BTC/USDT"


@pytest.mark.parametrize(
    "symbol",
    [
        "",
        " ",
        "\t",
        "\n",
    ],
)
def test_empty_symbol_is_rejected(
    engine,
    symbol,
):

    with pytest.raises(
        ValueError,
        match="symbol cannot be empty",
    ):

        engine.execute(
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
def test_invalid_symbol_type_is_rejected(
    engine,
    symbol,
):

    with pytest.raises(
        TypeError,
        match="symbol must be a string",
    ):

        engine.execute(
            symbol=symbol,
            side="buy",
            quantity=1.0,
            price=100.0,
        )


@pytest.mark.parametrize(
    "side",
    [
        "",
        " ",
        "hold",
        "long",
        "short",
        "buy_sell",
    ],
)
def test_invalid_side_is_rejected(
    engine,
    side,
):

    with pytest.raises(
        ValueError,
        match="side must be 'buy' or 'sell'",
    ):

        engine.execute(
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
def test_invalid_side_type_is_rejected(
    engine,
    side,
):

    with pytest.raises(
        TypeError,
        match="side must be a string",
    ):

        engine.execute(
            symbol="BTC/USDT",
            side=side,
            quantity=1.0,
            price=100.0,
        )


@pytest.mark.parametrize(
    "quantity",
    [
        0,
        -1,
        -0.1,
    ],
)
def test_non_positive_quantity_is_rejected(
    engine,
    quantity,
):

    with pytest.raises(
        ValueError,
        match="quantity must be greater than zero",
    ):

        engine.execute(
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
        True,
        False,
    ],
)
def test_invalid_quantity_type_is_rejected(
    engine,
    quantity,
):

    with pytest.raises(
        TypeError,
        match="quantity must be a number",
    ):

        engine.execute(
            symbol="BTC/USDT",
            side="buy",
            quantity=quantity,
            price=100.0,
        )


@pytest.mark.parametrize(
    "quantity",
    [
        float("inf"),
        float("-inf"),
        float("nan"),
    ],
)
def test_non_finite_quantity_is_rejected(
    engine,
    quantity,
):

    with pytest.raises(
        ValueError,
        match="quantity must be finite",
    ):

        engine.execute(
            symbol="BTC/USDT",
            side="buy",
            quantity=quantity,
            price=100.0,
        )


@pytest.mark.parametrize(
    "price",
    [
        0,
        -1,
        -0.1,
    ],
)
def test_non_positive_price_is_rejected(
    engine,
    price,
):

    with pytest.raises(
        ValueError,
        match="price must be greater than zero",
    ):

        engine.execute(
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
        True,
        False,
    ],
)
def test_invalid_price_type_is_rejected(
    engine,
    price,
):

    with pytest.raises(
        TypeError,
        match="price must be a number",
    ):

        engine.execute(
            symbol="BTC/USDT",
            side="buy",
            quantity=1.0,
            price=price,
        )


@pytest.mark.parametrize(
    "price",
    [
        float("inf"),
        float("-inf"),
        float("nan"),
    ],
)
def test_non_finite_price_is_rejected(
    engine,
    price,
):

    with pytest.raises(
        ValueError,
        match="price must be finite",
    ):

        engine.execute(
            symbol="BTC/USDT",
            side="buy",
            quantity=1.0,
            price=price,
        )


def test_multiple_trades_are_stored_in_order(
    engine,
):

    first = engine.execute(
        symbol="BTC/USDT",
        side="buy",
        quantity=1.0,
        price=100.0,
    )

    second = engine.execute(
        symbol="ETH/USDT",
        side="sell",
        quantity=2.0,
        price=200.0,
    )

    history = engine.history()

    assert history == [
        first,
        second,
    ]


def test_empty_history(
    engine,
):

    assert engine.history() == []


def test_history_returns_copy(
    engine,
):

    engine.execute(
        symbol="BTC/USDT",
        side="buy",
        quantity=1.0,
        price=100.0,
    )

    history = engine.history()

    history.clear()

    assert len(
        engine.history(),
    ) == 1


def test_each_execution_creates_independent_trade(
    engine,
):

    first = engine.execute(
        symbol="BTC/USDT",
        side="buy",
        quantity=1.0,
        price=100.0,
    )

    second = engine.execute(
        symbol="BTC/USDT",
        side="buy",
        quantity=2.0,
        price=200.0,
    )

    assert first is not second

    assert first.quantity == 1.0

    assert second.quantity == 2.0


def test_trade_timestamp_is_not_in_the_future(
    engine,
):

    before = datetime.now(UTC)

    trade = engine.execute(
        symbol="BTC/USDT",
        side="buy",
        quantity=1.0,
        price=100.0,
    )

    after = datetime.now(UTC)

    assert before <= trade.timestamp <= after