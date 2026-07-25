"""Tests for validated risk-gated execution."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta, timezone
from fractions import Fraction
from math import inf, nan
from unittest.mock import Mock

import pytest

from src.domain.order import Order
from src.execution.execution_engine import (
    ExecutionEngine,
    ExecutionRequest,
)
from src.execution.order_tracker import (
    OrderStatus,
    OrderTracker,
)
from src.risk.portfolio_guard import (
    PortfolioState,
)


FIXED_TIME = datetime(
    2026,
    7,
    25,
    12,
    0,
    tzinfo=UTC,
)


def make_portfolio() -> PortfolioState:
    return PortfolioState(
        balance=10_000.0,
        equity=10_000.0,
        used_margin=0.0,
        open_positions=0,
        daily_loss=0.0,
        total_risk=0.0,
    )


def make_request(
    **overrides: object,
) -> ExecutionRequest:
    values: dict[str, object] = {
        "symbol": "BTC/USDT",
        "quantity": 1.0,
        "price": 100.0,
        "leverage": 2.0,
        "stop_loss": 95.0,
        "portfolio": make_portfolio(),
        "side": "BUY",
        "order_type": "LIMIT",
    }
    values.update(overrides)

    return ExecutionRequest(
        **values,  # type: ignore[arg-type]
    )


@pytest.fixture
def risk() -> Mock:
    value = Mock()
    value.validate_trade.return_value = True
    return value


@pytest.fixture
def exchange() -> Mock:
    value = Mock()
    value.place_order.return_value = (
        "exchange-order-1"
    )
    return value


@pytest.fixture
def tracker() -> OrderTracker:
    return OrderTracker()


@pytest.fixture
def engine(
    risk: Mock,
    exchange: Mock,
    tracker: OrderTracker,
) -> ExecutionEngine:
    return ExecutionEngine(
        risk=risk,
        exchange=exchange,
        tracker=tracker,
        clock=lambda: FIXED_TIME,
    )


def test_execute_success(
    engine: ExecutionEngine,
    risk: Mock,
    exchange: Mock,
    tracker: OrderTracker,
) -> None:
    result = engine.execute(
        make_request()
    )

    assert result is True
    risk.validate_trade.assert_called_once()
    exchange.place_order.assert_called_once()
    assert tracker.exists(
        "exchange-order-1"
    ) is True


def test_risk_rejection_prevents_execution(
    engine: ExecutionEngine,
    risk: Mock,
    exchange: Mock,
    tracker: OrderTracker,
) -> None:
    risk.validate_trade.return_value = False

    result = engine.execute(
        make_request()
    )

    assert result is False
    exchange.place_order.assert_not_called()
    assert len(tracker) == 0


def test_order_is_built_correctly(
    engine: ExecutionEngine,
    exchange: Mock,
) -> None:
    engine.execute(
        make_request(
            symbol="eth/usdt",
            side="SELL",
            order_type="MARKET",
        )
    )

    order = exchange.place_order.call_args.args[0]

    assert isinstance(order, Order)
    assert order.symbol == "ETH/USDT"
    assert order.side == "SELL"
    assert order.order_type == "market"
    assert order.quantity == 1.0
    assert order.price == 100.0


def test_order_status_is_sent(
    engine: ExecutionEngine,
    tracker: OrderTracker,
) -> None:
    engine.execute(make_request())

    state = tracker.get(
        "exchange-order-1"
    )

    assert state.status is OrderStatus.SENT
    assert state.updated_at == FIXED_TIME


def test_tracker_contains_correct_order_data(
    engine: ExecutionEngine,
    tracker: OrderTracker,
) -> None:
    engine.execute(
        make_request(
            quantity=3.5,
            price=150.0,
        )
    )

    state = tracker.get(
        "exchange-order-1"
    )

    assert state.symbol == "BTC/USDT"
    assert state.quantity == 3.5
    assert state.price == 150.0


def test_risk_receives_expected_values(
    engine: ExecutionEngine,
    risk: Mock,
) -> None:
    request = make_request(
        quantity=2.5,
        price=250.0,
        leverage=3.0,
        stop_loss=225.0,
    )

    engine.execute(request)

    risk.validate_trade.assert_called_once_with(
        portfolio=request.portfolio,
        position_size=2.5,
        leverage=3.0,
        entry_price=250.0,
        stop_loss=225.0,
    )


def test_request_is_not_mutated(
    engine: ExecutionEngine,
) -> None:
    request = make_request(
        symbol="  btc/usdt  ",
        side=" sell ",
        order_type=" market ",
        quantity=1,
        price=100,
    )

    engine.execute(request)

    assert request.symbol == "  btc/usdt  "
    assert request.side == " sell "
    assert request.order_type == " market "
    assert request.quantity == 1
    assert request.price == 100


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("buy", "BUY"),
        ("BUY", "BUY"),
        (" Buy ", "BUY"),
        ("sell", "SELL"),
        ("SELL", "SELL"),
        (" Sell ", "SELL"),
    ],
)
def test_side_normalization(
    engine: ExecutionEngine,
    exchange: Mock,
    source: str,
    expected: str,
) -> None:
    engine.execute(
        make_request(
            side=source,
        )
    )

    order = exchange.place_order.call_args.args[0]

    assert order.side == expected


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("market", "market"),
        ("MARKET", "market"),
        (" Market ", "market"),
        ("limit", "limit"),
        ("LIMIT", "limit"),
        (" Limit ", "limit"),
    ],
)
def test_order_type_normalization(
    engine: ExecutionEngine,
    exchange: Mock,
    source: str,
    expected: str,
) -> None:
    engine.execute(
        make_request(
            order_type=source,
        )
    )

    order = exchange.place_order.call_args.args[0]

    assert order.order_type == expected


def test_symbol_normalization(
    engine: ExecutionEngine,
    exchange: Mock,
) -> None:
    engine.execute(
        make_request(
            symbol="  btc/usdt  ",
        )
    )

    order = exchange.place_order.call_args.args[0]

    assert order.symbol == "BTC/USDT"


def test_fraction_numbers_are_supported(
    engine: ExecutionEngine,
    exchange: Mock,
    risk: Mock,
) -> None:
    request = make_request(
        quantity=Fraction(1, 2),
        price=Fraction(201, 2),
        leverage=Fraction(2, 1),
        stop_loss=Fraction(95, 1),
    )

    engine.execute(request)

    order = exchange.place_order.call_args.args[0]

    assert order.quantity == 0.5
    assert order.price == 100.5
    risk.validate_trade.assert_called_once_with(
        portfolio=request.portfolio,
        position_size=0.5,
        leverage=2.0,
        entry_price=100.5,
        stop_loss=95.0,
    )


@pytest.mark.parametrize(
    "invalid_request",
    [
        None,
        1,
        True,
        "request",
        [],
        {},
        object(),
    ],
)
def test_invalid_request_type(
    engine: ExecutionEngine,
    invalid_request: object,
) -> None:
    with pytest.raises(
        TypeError,
        match=(
            "request must be an "
            "ExecutionRequest"
        ),
    ):
        engine.execute(
            invalid_request  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "symbol",
    ["", " ", "\t", "\n"],
)
def test_empty_symbol(
    engine: ExecutionEngine,
    symbol: str,
) -> None:
    with pytest.raises(
        ValueError,
        match="Symbol cannot be empty",
    ):
        engine.execute(
            make_request(
                symbol=symbol,
            )
        )


@pytest.mark.parametrize(
    "symbol",
    [None, 123, True, [], {}, object()],
)
def test_invalid_symbol_type(
    engine: ExecutionEngine,
    symbol: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="Symbol must be a string",
    ):
        engine.execute(
            make_request(
                symbol=symbol,
            )
        )


def test_symbol_length_is_bounded(
    engine: ExecutionEngine,
) -> None:
    with pytest.raises(
        ValueError,
        match=(
            "Symbol must not exceed "
            "100 characters"
        ),
    ):
        engine.execute(
            make_request(
                symbol="x" * 101,
            )
        )


@pytest.mark.parametrize(
    ("field", "label"),
    [
        ("quantity", "Quantity"),
        ("price", "Price"),
        ("leverage", "Leverage"),
        ("stop_loss", "Stop loss"),
    ],
)
@pytest.mark.parametrize(
    "value",
    [0, -1, -0.1],
)
def test_non_positive_numeric_field(
    engine: ExecutionEngine,
    field: str,
    label: str,
    value: float,
) -> None:
    with pytest.raises(
        ValueError,
        match=(
            f"{label} must be greater "
            "than zero"
        ),
    ):
        engine.execute(
            make_request(
                **{
                    field: value,
                }
            )
        )


@pytest.mark.parametrize(
    ("field", "label"),
    [
        ("quantity", "Quantity"),
        ("price", "Price"),
        ("leverage", "Leverage"),
        ("stop_loss", "Stop loss"),
    ],
)
@pytest.mark.parametrize(
    "value",
    [nan, inf, -inf],
)
def test_non_finite_numeric_field(
    engine: ExecutionEngine,
    field: str,
    label: str,
    value: float,
) -> None:
    with pytest.raises(
        ValueError,
        match=f"{label} must be finite",
    ):
        engine.execute(
            make_request(
                **{
                    field: value,
                }
            )
        )


@pytest.mark.parametrize(
    ("field", "label"),
    [
        ("quantity", "Quantity"),
        ("price", "Price"),
        ("leverage", "Leverage"),
        ("stop_loss", "Stop loss"),
    ],
)
@pytest.mark.parametrize(
    "value",
    [
        None,
        "1",
        True,
        False,
        [],
        {},
        object(),
    ],
)
def test_invalid_numeric_field_type(
    engine: ExecutionEngine,
    field: str,
    label: str,
    value: object,
) -> None:
    with pytest.raises(
        TypeError,
        match=f"{label} must be a number",
    ):
        engine.execute(
            make_request(
                **{
                    field: value,
                }
            )
        )


def test_trade_notional_overflow(
    engine: ExecutionEngine,
    risk: Mock,
    exchange: Mock,
) -> None:
    with pytest.raises(
        ValueError,
        match="Trade notional must be finite",
    ):
        engine.execute(
            make_request(
                quantity=1e308,
                price=1e308,
            )
        )

    risk.validate_trade.assert_not_called()
    exchange.place_order.assert_not_called()


@pytest.mark.parametrize(
    "side",
    ["", " ", "HOLD", "BUYSELL", "LONG"],
)
def test_invalid_side_value(
    engine: ExecutionEngine,
    side: str,
) -> None:
    with pytest.raises(
        ValueError,
        match="Side must be BUY or SELL",
    ):
        engine.execute(
            make_request(side=side)
        )


@pytest.mark.parametrize(
    "side",
    [None, 1, True, [], {}, object()],
)
def test_invalid_side_type(
    engine: ExecutionEngine,
    side: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="Side must be a string",
    ):
        engine.execute(
            make_request(side=side)
        )


@pytest.mark.parametrize(
    "order_type",
    ["", " ", "STOP", "UNKNOWN"],
)
def test_invalid_order_type_value(
    engine: ExecutionEngine,
    order_type: str,
) -> None:
    with pytest.raises(
        ValueError,
        match=(
            "Order type must be "
            "MARKET or LIMIT"
        ),
    ):
        engine.execute(
            make_request(
                order_type=order_type,
            )
        )


@pytest.mark.parametrize(
    "order_type",
    [None, 1, True, [], {}, object()],
)
def test_invalid_order_type_type(
    engine: ExecutionEngine,
    order_type: object,
) -> None:
    with pytest.raises(
        TypeError,
        match=(
            "Order type must be a string"
        ),
    ):
        engine.execute(
            make_request(
                order_type=order_type,
            )
        )


@pytest.mark.parametrize(
    "portfolio",
    [None, 1, True, {}, object()],
)
def test_invalid_portfolio_type(
    engine: ExecutionEngine,
    portfolio: object,
) -> None:
    with pytest.raises(
        TypeError,
        match=(
            "Portfolio must be a "
            "PortfolioState"
        ),
    ):
        engine.execute(
            make_request(
                portfolio=portfolio,
            )
        )


@pytest.mark.parametrize(
    "approved",
    [1, 0, None, "yes", object()],
)
def test_invalid_risk_return_type(
    engine: ExecutionEngine,
    risk: Mock,
    approved: object,
) -> None:
    risk.validate_trade.return_value = approved

    with pytest.raises(
        TypeError,
        match=(
            "risk.validate_trade must "
            "return a bool"
        ),
    ):
        engine.execute(
            make_request()
        )


def test_risk_exception_propagates(
    engine: ExecutionEngine,
    risk: Mock,
    exchange: Mock,
) -> None:
    risk.validate_trade.side_effect = (
        RuntimeError("risk unavailable")
    )

    with pytest.raises(
        RuntimeError,
        match="risk unavailable",
    ):
        engine.execute(make_request())

    exchange.place_order.assert_not_called()


def test_exchange_exception_propagates(
    engine: ExecutionEngine,
    exchange: Mock,
    tracker: OrderTracker,
) -> None:
    exchange.place_order.side_effect = (
        RuntimeError("exchange unavailable")
    )

    with pytest.raises(
        RuntimeError,
        match="exchange unavailable",
    ):
        engine.execute(make_request())

    assert len(tracker) == 0


@pytest.mark.parametrize(
    "order_id",
    [
        None,
        "",
        " ",
        "\t",
        False,
        True,
        0,
    ],
)
def test_unusable_exchange_order_id_fails(
    engine: ExecutionEngine,
    exchange: Mock,
    tracker: OrderTracker,
    order_id: object,
) -> None:
    exchange.place_order.return_value = order_id

    result = engine.execute(
        make_request()
    )

    assert result is False
    assert len(tracker) == 0


def test_exchange_order_id_is_stringified(
    engine: ExecutionEngine,
    exchange: Mock,
    tracker: OrderTracker,
) -> None:
    exchange.place_order.return_value = 12345

    assert engine.execute(
        make_request()
    ) is True
    assert tracker.exists("12345") is True


def test_exchange_order_id_is_trimmed(
    engine: ExecutionEngine,
    exchange: Mock,
    tracker: OrderTracker,
) -> None:
    exchange.place_order.return_value = (
        "  exchange-order-1  "
    )

    assert engine.execute(
        make_request()
    ) is True
    assert tracker.exists(
        "exchange-order-1"
    ) is True


def test_oversized_exchange_order_id_fails(
    engine: ExecutionEngine,
    exchange: Mock,
    tracker: OrderTracker,
) -> None:
    exchange.place_order.return_value = (
        "x" * 201
    )

    assert engine.execute(
        make_request()
    ) is False
    assert len(tracker) == 0


def test_duplicate_tracker_id_propagates(
    engine: ExecutionEngine,
    tracker: OrderTracker,
) -> None:
    assert engine.execute(
        make_request()
    ) is True

    with pytest.raises(
        ValueError,
        match="Order already exists",
    ):
        engine.execute(
            make_request()
        )

    assert len(tracker) == 1


def test_clock_is_validated_before_exchange(
    risk: Mock,
    exchange: Mock,
    tracker: OrderTracker,
) -> None:
    engine = ExecutionEngine(
        risk=risk,
        exchange=exchange,
        tracker=tracker,
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
        match=(
            "clock must return a "
            "timezone-aware datetime"
        ),
    ):
        engine.execute(
            make_request()
        )

    exchange.place_order.assert_not_called()
    assert len(tracker) == 0


def test_clock_timestamp_is_normalized_to_utc(
    risk: Mock,
    exchange: Mock,
    tracker: OrderTracker,
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
    engine = ExecutionEngine(
        risk=risk,
        exchange=exchange,
        tracker=tracker,
        clock=lambda: source,
    )

    engine.execute(make_request())

    state = tracker.get(
        "exchange-order-1"
    )

    assert state.updated_at == FIXED_TIME
    assert state.updated_at.tzinfo is UTC


def test_invalid_clock_dependency(
    risk: Mock,
    exchange: Mock,
    tracker: OrderTracker,
) -> None:
    with pytest.raises(
        TypeError,
        match="clock must be callable",
    ):
        ExecutionEngine(
            risk=risk,
            exchange=exchange,
            tracker=tracker,
            clock=1,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        (
            "risk",
            object(),
            "risk must provide",
        ),
        (
            "exchange",
            object(),
            "exchange must provide",
        ),
        (
            "tracker",
            object(),
            "tracker must provide",
        ),
    ],
)
def test_invalid_dependency(
    risk: Mock,
    exchange: Mock,
    tracker: OrderTracker,
    field: str,
    value: object,
    message: str,
) -> None:
    dependencies: dict[str, object] = {
        "risk": risk,
        "exchange": exchange,
        "tracker": tracker,
    }
    dependencies[field] = value

    with pytest.raises(
        TypeError,
        match=message,
    ):
        ExecutionEngine(
            **dependencies,  # type: ignore[arg-type]
        )


def test_private_build_order_legacy_contract(
    engine: ExecutionEngine,
) -> None:
    order = engine._build_order(
        make_request(
            symbol=" eth/usdt ",
            side="sell",
            order_type="market",
            quantity=2,
            price=200,
        )
    )

    assert order == Order(
        symbol="ETH/USDT",
        side="SELL",
        order_type="market",
        quantity=2.0,
        price=200.0,
    )


def test_concurrent_execution_with_unique_ids() -> None:
    risk = Mock()
    risk.validate_trade.return_value = True

    class Exchange:
        def place_order(
            self,
            order: Order,
        ) -> str:
            return order.symbol

    tracker = OrderTracker()
    engine = ExecutionEngine(
        risk=risk,
        exchange=Exchange(),  # type: ignore[arg-type]
        tracker=tracker,
        clock=lambda: FIXED_TIME,
    )

    requests = [
        make_request(
            symbol=f"ASSET-{index}",
        )
        for index in range(250)
    ]

    with ThreadPoolExecutor(
        max_workers=16,
    ) as executor:
        results = list(
            executor.map(
                engine.execute,
                requests,
            )
        )

    assert all(
        result is True
        for result in results
    )
    assert len(tracker) == 250