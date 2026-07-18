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
    **overrides,
) -> ExecutionRequest:

    data = {
        "symbol": "BTC/USDT",
        "quantity": 1.0,
        "price": 100.0,
        "leverage": 2.0,
        "stop_loss": 95.0,
        "portfolio": make_portfolio(),
    }

    data.update(overrides)

    return ExecutionRequest(
        **data
    )


@pytest.fixture
def risk():

    risk = Mock()

    risk.validate_trade.return_value = True

    return risk


@pytest.fixture
def exchange():

    exchange = Mock()

    exchange.place_order.return_value = (
        "exchange-order-1"
    )

    return exchange


@pytest.fixture
def tracker():

    return OrderTracker()


@pytest.fixture
def engine(
    risk,
    exchange,
    tracker,
):

    return ExecutionEngine(
        risk=risk,
        exchange=exchange,
        tracker=tracker,
    )


def test_execute_success(
    engine,
    risk,
    exchange,
    tracker,
):

    result = engine.execute(
        make_request()
    )

    assert result is True

    risk.validate_trade.assert_called_once()

    exchange.place_order.assert_called_once()

    assert tracker.exists(
        "exchange-order-1"
    )


def test_risk_rejection_prevents_execution(
    engine,
    risk,
    exchange,
    tracker,
):

    risk.validate_trade.return_value = False

    result = engine.execute(
        make_request()
    )

    assert result is False

    exchange.place_order.assert_not_called()

    assert tracker.exists(
        "exchange-order-1"
    ) is False


def test_order_is_built_correctly(
    engine,
    exchange,
):

    engine.execute(
        make_request(
            symbol="eth/usdt",
            side="SELL",
            order_type="MARKET",
        )
    )

    order = (
        exchange
        .place_order
        .call_args
        .args[0]
    )

    assert isinstance(
        order,
        Order,
    )

    assert order.symbol == "ETH/USDT"

    assert order.side == "SELL"

    assert order.order_type == "market"

    assert order.quantity == 1.0

    assert order.price == 100.0


def test_order_status_is_sent(
    engine,
    tracker,
):

    engine.execute(
        make_request()
    )

    state = tracker.get(
        "exchange-order-1"
    )

    assert state.status == OrderStatus.SENT


@pytest.mark.parametrize(
    "quantity",
    [
        0,
        -1,
    ],
)
def test_invalid_quantity(
    engine,
    quantity,
):

    with pytest.raises(
        ValueError,
    ):

        engine.execute(
            make_request(
                quantity=quantity
            )
        )


@pytest.mark.parametrize(
    "price",
    [
        0,
        -1,
    ],
)
def test_invalid_price(
    engine,
    price,
):

    with pytest.raises(
        ValueError,
    ):

        engine.execute(
            make_request(
                price=price
            )
        )


@pytest.mark.parametrize(
    "leverage",
    [
        0,
        -1,
    ],
)
def test_invalid_leverage(
    engine,
    leverage,
):

    with pytest.raises(
        ValueError,
    ):

        engine.execute(
            make_request(
                leverage=leverage
            )
        )


@pytest.mark.parametrize(
    "stop_loss",
    [
        0,
        -1,
    ],
)
def test_invalid_stop_loss(
    engine,
    stop_loss,
):

    with pytest.raises(
        ValueError,
    ):

        engine.execute(
            make_request(
                stop_loss=stop_loss
            )
        )


@pytest.mark.parametrize(
    "side",
    [
        "",
        "HOLD",
        "BUYSELL",
    ],
)
def test_invalid_side(
    engine,
    side,
):

    with pytest.raises(
        ValueError,
    ):

        engine.execute(
            make_request(
                side=side
            )
        )


@pytest.mark.parametrize(
    "order_type",
    [
        "",
        "STOP",
        "UNKNOWN",
    ],
)
def test_invalid_order_type(
    engine,
    order_type,
):

    with pytest.raises(
        ValueError,
    ):

        engine.execute(
            make_request(
                order_type=order_type
            )
        )


@pytest.mark.parametrize(
    "symbol",
    [
        "",
        " ",
        "\t",
    ],
)
def test_empty_symbol(
    engine,
    symbol,
):

    with pytest.raises(
        ValueError,
    ):

        engine.execute(
            make_request(
                symbol=symbol
            )
        )


def test_invalid_symbol_type(
    engine,
):

    with pytest.raises(
        TypeError,
    ):

        engine.execute(
            make_request(
                symbol=123
            )
        )


def test_exchange_order_id_is_stringified(
    engine,
    exchange,
    tracker,
):

    exchange.place_order.return_value = 12345

    result = engine.execute(
        make_request()
    )

    assert result is True

    assert tracker.exists(
        "12345"
    )


def test_empty_exchange_order_id_fails(
    engine,
    exchange,
    tracker,
):

    exchange.place_order.return_value = ""

    result = engine.execute(
        make_request()
    )

    assert result is False

    assert tracker.exists(
        "exchange-order-1"
    ) is False


def test_risk_receives_expected_values(
    engine,
    risk,
):

    request = make_request(
        quantity=2.5,
        price=250.0,
        leverage=3.0,
        stop_loss=225.0,
    )

    engine.execute(
        request
    )

    risk.validate_trade.assert_called_once_with(
        portfolio=request.portfolio,
        position_size=2.5,
        leverage=3.0,
        entry_price=250.0,
        stop_loss=225.0,
    )


def test_symbol_is_normalized(
    engine,
    exchange,
):

    engine.execute(
        make_request(
            symbol="  btc/usdt  "
        )
    )

    order = (
        exchange
        .place_order
        .call_args
        .args[0]
    )

    assert order.symbol == "BTC/USDT"


def test_side_is_normalized(
    engine,
    exchange,
):

    engine.execute(
        make_request(
            side="sell"
        )
    )

    order = (
        exchange
        .place_order
        .call_args
        .args[0]
    )

    assert order.side == "SELL"


def test_order_type_is_normalized(
    engine,
    exchange,
):

    engine.execute(
        make_request(
            order_type="LIMIT"
        )
    )

    order = (
        exchange
        .place_order
        .call_args
        .args[0]
    )

    assert order.order_type == "limit"


def test_tracker_contains_correct_order_data(
    engine,
    tracker,
):

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


def test_exchange_called_only_after_risk_approval(
    engine,
    risk,
    exchange,
):

    risk.validate_trade.return_value = False

    engine.execute(
        make_request()
    )

    risk.validate_trade.assert_called_once()

    exchange.place_order.assert_not_called()