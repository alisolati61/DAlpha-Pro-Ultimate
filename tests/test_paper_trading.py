"""Tests for validated thread-safe paper-trading execution."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta, timezone
from fractions import Fraction
from math import inf, nan

import pytest

from src.execution.paper_trading import (
    PaperTrade,
    PaperTradeSide,
    PaperTradingEngine,
)


FIXED_TIME = datetime(
    2026,
    7,
    25,
    12,
    0,
    tzinfo=UTC,
)


@pytest.fixture
def engine() -> PaperTradingEngine:
    return PaperTradingEngine(
        clock=lambda: FIXED_TIME,
    )


def execute(
    engine: PaperTradingEngine,
    **overrides: object,
) -> PaperTrade:
    values: dict[str, object] = {
        "symbol": "BTC/USDT",
        "side": "buy",
        "quantity": 1.0,
        "price": 100.0,
    }
    values.update(overrides)

    return engine.execute(
        **values,  # type: ignore[arg-type]
    )


def test_side_enum_values() -> None:
    assert PaperTradeSide.BUY.value == "buy"
    assert PaperTradeSide.SELL.value == "sell"


def test_execute_returns_trade(
    engine: PaperTradingEngine,
) -> None:
    trade = execute(engine)

    assert isinstance(trade, PaperTrade)
    assert trade.symbol == "BTC/USDT"
    assert trade.side == "buy"
    assert trade.quantity == 1.0
    assert trade.entry_price == 100.0
    assert trade.timestamp == FIXED_TIME


def test_execute_stores_same_immutable_trade(
    engine: PaperTradingEngine,
) -> None:
    trade = execute(engine)

    assert engine.history() == [trade]
    assert engine.latest() is trade


def test_trade_is_immutable(
    engine: PaperTradingEngine,
) -> None:
    trade = execute(engine)

    with pytest.raises(FrozenInstanceError):
        trade.quantity = 2.0  # type: ignore[misc]


def test_trade_properties(
    engine: PaperTradingEngine,
) -> None:
    buy = execute(engine)
    sell = execute(
        engine,
        symbol="ETH/USDT",
        side="sell",
        quantity=2,
        price=50,
    )

    assert buy.notional_value == 100.0
    assert buy.is_buy is True
    assert buy.is_sell is False
    assert sell.notional_value == 100.0
    assert sell.is_buy is False
    assert sell.is_sell is True


def test_numeric_fields_are_exact_floats(
    engine: PaperTradingEngine,
) -> None:
    trade = execute(
        engine,
        quantity=1,
        price=100,
    )

    assert type(trade.quantity) is float
    assert type(trade.entry_price) is float
    assert type(trade.notional_value) is float


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("buy", "buy"),
        ("BUY", "buy"),
        (" Buy ", "buy"),
        ("sell", "sell"),
        ("SELL", "sell"),
        (" Sell ", "sell"),
        (PaperTradeSide.BUY, "buy"),
        (PaperTradeSide.SELL, "sell"),
    ],
)
def test_side_normalization(
    engine: PaperTradingEngine,
    source: PaperTradeSide | str,
    expected: str,
) -> None:
    trade = execute(
        engine,
        side=source,
    )

    assert trade.side == expected


def test_symbol_whitespace_is_stripped(
    engine: PaperTradingEngine,
) -> None:
    trade = execute(
        engine,
        symbol="  BTC/USDT  ",
    )

    assert trade.symbol == "BTC/USDT"


def test_fraction_numbers_are_supported(
    engine: PaperTradingEngine,
) -> None:
    trade = execute(
        engine,
        quantity=Fraction(1, 2),
        price=Fraction(201, 2),
    )

    assert trade.quantity == 0.5
    assert trade.entry_price == 100.5


@pytest.mark.parametrize(
    "symbol",
    ["", " ", "\t", "\n"],
)
def test_empty_symbol_rejected(
    engine: PaperTradingEngine,
    symbol: str,
) -> None:
    with pytest.raises(
        ValueError,
        match="symbol cannot be empty",
    ):
        execute(
            engine,
            symbol=symbol,
        )


@pytest.mark.parametrize(
    "symbol",
    [None, 123, True, [], {}, object()],
)
def test_invalid_symbol_type(
    engine: PaperTradingEngine,
    symbol: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="symbol must be a string",
    ):
        execute(
            engine,
            symbol=symbol,
        )


def test_symbol_length_is_bounded(
    engine: PaperTradingEngine,
) -> None:
    with pytest.raises(
        ValueError,
        match="symbol must not exceed 100 characters",
    ):
        execute(
            engine,
            symbol="x" * 101,
        )


@pytest.mark.parametrize(
    "side",
    ["", " ", "hold", "long", "short", "buy_sell"],
)
def test_invalid_side_value(
    engine: PaperTradingEngine,
    side: str,
) -> None:
    with pytest.raises(
        ValueError,
        match="side must be 'buy' or 'sell'",
    ):
        execute(
            engine,
            side=side,
        )


@pytest.mark.parametrize(
    "side",
    [None, 123, True, [], {}, object()],
)
def test_invalid_side_type(
    engine: PaperTradingEngine,
    side: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="side must be a string",
    ):
        execute(
            engine,
            side=side,
        )


@pytest.mark.parametrize(
    "field",
    ["quantity", "price"],
)
@pytest.mark.parametrize(
    "value",
    [0, -1, -0.1],
)
def test_non_positive_number_rejected(
    engine: PaperTradingEngine,
    field: str,
    value: float,
) -> None:
    with pytest.raises(
        ValueError,
        match=f"{field} must be greater than zero",
    ):
        execute(
            engine,
            **{field: value},
        )


@pytest.mark.parametrize(
    "field",
    ["quantity", "price"],
)
@pytest.mark.parametrize(
    "value",
    [nan, inf, -inf],
)
def test_non_finite_number_rejected(
    engine: PaperTradingEngine,
    field: str,
    value: float,
) -> None:
    with pytest.raises(
        ValueError,
        match=f"{field} must be finite",
    ):
        execute(
            engine,
            **{field: value},
        )


@pytest.mark.parametrize(
    "field",
    ["quantity", "price"],
)
@pytest.mark.parametrize(
    "value",
    [None, "1", [], {}, True, False, object()],
)
def test_invalid_number_type(
    engine: PaperTradingEngine,
    field: str,
    value: object,
) -> None:
    with pytest.raises(
        TypeError,
        match=f"{field} must be a number",
    ):
        execute(
            engine,
            **{field: value},
        )


def test_notional_overflow_is_rejected_atomically(
    engine: PaperTradingEngine,
) -> None:
    with pytest.raises(
        ValueError,
        match="trade notional must be finite",
    ):
        execute(
            engine,
            quantity=1e308,
            price=1e308,
        )

    assert engine.history() == []


def test_injected_timestamp(
    engine: PaperTradingEngine,
) -> None:
    trade = engine.execute(
        "BTC/USDT",
        "buy",
        1,
        100,
        timestamp=FIXED_TIME,
    )

    assert trade.timestamp == FIXED_TIME


def test_non_utc_timestamp_is_normalized(
    engine: PaperTradingEngine,
) -> None:
    source = datetime(
        2026,
        7,
        25,
        15,
        30,
        tzinfo=timezone(
            timedelta(hours=3, minutes=30)
        ),
    )

    trade = engine.execute(
        "BTC/USDT",
        "buy",
        1,
        100,
        timestamp=source,
    )

    assert trade.timestamp == FIXED_TIME
    assert trade.timestamp.tzinfo is UTC


def test_naive_timestamp_rejected(
    engine: PaperTradingEngine,
) -> None:
    with pytest.raises(
        ValueError,
        match="timestamp must be timezone-aware",
    ):
        engine.execute(
            "BTC/USDT",
            "buy",
            1,
            100,
            timestamp=datetime(
                2026,
                7,
                25,
                12,
                0,
            ),
        )


@pytest.mark.parametrize(
    "timestamp",
    [None, 1, True, "time", object()],
)
def test_invalid_explicit_timestamp_type(
    engine: PaperTradingEngine,
    timestamp: object,
) -> None:
    # ``None`` means use the engine clock and is therefore tested separately.
    if timestamp is None:
        trade = engine.execute(
            "BTC/USDT",
            "buy",
            1,
            100,
            timestamp=None,
        )
        assert trade.timestamp == FIXED_TIME
        return

    with pytest.raises(
        TypeError,
        match="timestamp must be a datetime",
    ):
        engine.execute(
            "BTC/USDT",
            "buy",
            1,
            100,
            timestamp=timestamp,  # type: ignore[arg-type]
        )


def test_invalid_clock_result_preserves_history() -> None:
    engine = PaperTradingEngine(
        clock=lambda: datetime(
            2026,
            7,
            25,
            12,
            0,
        ),
    )

    with pytest.raises(
        ValueError,
        match="timestamp must be timezone-aware",
    ):
        execute(engine)

    assert engine.history() == []


def test_invalid_clock_dependency() -> None:
    with pytest.raises(
        TypeError,
        match="clock must be callable",
    ):
        PaperTradingEngine(
            clock=1,  # type: ignore[arg-type]
        )


def test_history_order_and_independent_list(
    engine: PaperTradingEngine,
) -> None:
    first = execute(engine)
    second = execute(
        engine,
        symbol="ETH/USDT",
    )

    history = engine.history()

    assert history == [first, second]

    history.clear()

    assert engine.history() == [first, second]


def test_snapshot_and_iterator(
    engine: PaperTradingEngine,
) -> None:
    first = execute(engine)
    second = execute(
        engine,
        symbol="ETH/USDT",
    )

    iterator = iter(engine)
    engine.clear()

    assert engine.snapshot() == ()
    assert list(iterator) == [first, second]


def test_empty_engine_state(
    engine: PaperTradingEngine,
) -> None:
    assert engine.history() == []
    assert engine.snapshot() == ()
    assert engine.latest() is None
    assert engine.recent(5) == []
    assert len(engine) == 0
    assert bool(engine) is False
    assert engine.total_quantity() == 0.0
    assert engine.total_notional() == 0.0
    assert engine.is_full is False


def test_recent(
    engine: PaperTradingEngine,
) -> None:
    trades = [
        execute(
            engine,
            symbol=f"ASSET-{index}",
        )
        for index in range(5)
    ]

    assert engine.recent(2) == trades[-2:]
    assert engine.recent(100) == trades


@pytest.mark.parametrize(
    "limit",
    [0, -1],
)
def test_recent_invalid_limit_value(
    engine: PaperTradingEngine,
    limit: int,
) -> None:
    with pytest.raises(
        ValueError,
        match="limit must be greater than zero",
    ):
        engine.recent(limit)


@pytest.mark.parametrize(
    "limit",
    [True, False, 1.5, "1", None, object()],
)
def test_recent_invalid_limit_type(
    engine: PaperTradingEngine,
    limit: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="limit must be an integer",
    ):
        engine.recent(
            limit  # type: ignore[arg-type]
        )


def test_filters(
    engine: PaperTradingEngine,
) -> None:
    btc_buy = execute(
        engine,
        symbol="BTC/USDT",
        side="buy",
    )
    eth_sell = execute(
        engine,
        symbol="ETH/USDT",
        side="sell",
    )
    btc_sell = execute(
        engine,
        symbol="BTC/USDT",
        side="sell",
    )

    assert engine.for_symbol(
        " BTC/USDT "
    ) == [btc_buy, btc_sell]
    assert engine.by_side("BUY") == [btc_buy]
    assert engine.by_side(
        PaperTradeSide.SELL
    ) == [eth_sell, btc_sell]


def test_aggregates(
    engine: PaperTradingEngine,
) -> None:
    execute(
        engine,
        side="buy",
        quantity=2,
        price=100,
    )
    execute(
        engine,
        symbol="ETH/USDT",
        side="sell",
        quantity=3,
        price=50,
    )

    assert engine.total_quantity() == 5.0
    assert engine.total_quantity(
        side="buy"
    ) == 2.0
    assert engine.total_quantity(
        side="sell"
    ) == 3.0
    assert engine.total_notional() == 350.0
    assert engine.total_notional(
        side="BUY"
    ) == 200.0


def test_clear(
    engine: PaperTradingEngine,
) -> None:
    execute(engine)

    result = engine.clear()

    assert result is None
    assert engine.history() == []


def test_bounded_history_evicts_oldest() -> None:
    engine = PaperTradingEngine(
        clock=lambda: FIXED_TIME,
        max_history=2,
    )
    first = execute(
        engine,
        symbol="FIRST",
    )
    second = execute(
        engine,
        symbol="SECOND",
    )
    third = execute(
        engine,
        symbol="THIRD",
    )

    assert engine.history() == [
        second,
        third,
    ]
    assert first not in engine.history()
    assert engine.max_history == 2
    assert engine.is_full is True


@pytest.mark.parametrize(
    "max_history",
    [0, -1],
)
def test_invalid_max_history_value(
    max_history: int,
) -> None:
    with pytest.raises(
        ValueError,
        match="max_history must be greater than zero",
    ):
        PaperTradingEngine(
            max_history=max_history
        )


@pytest.mark.parametrize(
    "max_history",
    [True, False, 1.5, "10", [], object()],
)
def test_invalid_max_history_type(
    max_history: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="max_history must be an integer or None",
    ):
        PaperTradingEngine(
            max_history=max_history,  # type: ignore[arg-type]
        )


def test_trade_timestamp_is_not_in_future() -> None:
    engine = PaperTradingEngine()
    before = datetime.now(UTC)

    trade = execute(engine)

    after = datetime.now(UTC)

    assert before <= trade.timestamp <= after


def test_concurrent_execution_is_safe() -> None:
    engine = PaperTradingEngine(
        clock=lambda: FIXED_TIME,
    )

    def run(index: int) -> PaperTrade:
        return engine.execute(
            symbol=f"ASSET-{index}",
            side="buy",
            quantity=1,
            price=100,
        )

    with ThreadPoolExecutor(
        max_workers=16,
    ) as executor:
        trades = list(
            executor.map(
                run,
                range(500),
            )
        )

    assert len(engine) == 500
    assert len(trades) == 500
    assert len(
        {
            trade.symbol
            for trade in engine.snapshot()
        }
    ) == 500