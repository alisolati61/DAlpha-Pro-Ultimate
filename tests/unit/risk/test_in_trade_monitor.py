import math

import pytest

from src.risk.drawdown_guard import DrawdownGuard
from src.risk.in_trade_monitor import (
    InTradeMonitor,
    TradeState,
)
from src.risk.kill_switch import KillSwitch


@pytest.fixture
def drawdown_guard():

    return DrawdownGuard(
        max_drawdown=0.15,
    )


@pytest.fixture
def kill_switch():

    return KillSwitch()


@pytest.fixture
def monitor(
    drawdown_guard,
    kill_switch,
):

    return InTradeMonitor(
        drawdown_guard=drawdown_guard,
        kill_switch=kill_switch,
    )


def make_trade(**overrides):

    data = {
        "entry_price": 100.0,
        "current_price": 105.0,
        "stop_loss": 95.0,
        "peak_balance": 10_000.0,
        "current_balance": 9_500.0,
    }

    data.update(overrides)

    return TradeState(**data)


def test_trade_can_continue_when_risk_is_valid(
    monitor,
):

    assert monitor.monitor(
        make_trade()
    ) is True


def test_active_kill_switch_blocks_trade(
    monitor,
    kill_switch,
):

    kill_switch.activate(
        "Manual emergency stop"
    )

    assert monitor.monitor(
        make_trade()
    ) is False

    assert kill_switch.reason == (
        "Manual emergency stop"
    )


def test_drawdown_breach_blocks_trade(
    monitor,
    kill_switch,
):

    trade = make_trade(
        current_balance=8_500.0,
    )

    assert monitor.monitor(
        trade
    ) is False

    assert kill_switch.active is True

    assert kill_switch.reason == (
        "Maximum drawdown exceeded"
    )


def test_drawdown_breach_activates_kill_switch(
    monitor,
    kill_switch,
):

    assert kill_switch.active is False

    monitor.monitor(
        make_trade(
            current_balance=8_000.0,
        )
    )

    assert kill_switch.active is True


def test_drawdown_at_exact_limit_is_blocked(
    monitor,
):

    trade = make_trade(
        current_balance=8_500.0,
    )

    assert monitor.monitor(
        trade
    ) is False


def test_drawdown_below_limit_is_allowed(
    monitor,
    kill_switch,
):

    trade = make_trade(
        current_balance=8_501.0,
    )

    assert monitor.monitor(
        trade
    ) is True

    assert kill_switch.active is False


def test_existing_kill_switch_reason_is_preserved(
    monitor,
    kill_switch,
):

    kill_switch.activate(
        "Manual emergency stop"
    )

    assert monitor.monitor(
        make_trade(
            current_balance=8_000.0,
        )
    ) is False

    assert kill_switch.reason == (
        "Manual emergency stop"
    )


def test_trade_state_is_immutable():

    trade = make_trade()

    with pytest.raises(
        AttributeError,
    ):

        trade.current_price = 200.0


def test_invalid_trade_type_is_rejected(
    monitor,
):

    with pytest.raises(
        TypeError,
        match="trade must be a TradeState",
    ):

        monitor.monitor(None)


@pytest.mark.parametrize(
    "field",
    [
        "entry_price",
        "current_price",
        "stop_loss",
    ],
)
def test_zero_price_is_rejected(
    monitor,
    field,
):

    trade = make_trade(
        **{
            field: 0,
        }
    )

    with pytest.raises(
        ValueError,
        match="greater than zero",
    ):

        monitor.monitor(trade)


@pytest.mark.parametrize(
    "field",
    [
        "entry_price",
        "current_price",
        "stop_loss",
    ],
)
def test_negative_price_is_rejected(
    monitor,
    field,
):

    trade = make_trade(
        **{
            field: -1,
        }
    )

    with pytest.raises(
        ValueError,
        match="greater than zero",
    ):

        monitor.monitor(trade)


@pytest.mark.parametrize(
    "field",
    [
        "entry_price",
        "current_price",
        "stop_loss",
    ],
)
def test_nan_price_is_rejected(
    monitor,
    field,
):

    trade = make_trade(
        **{
            field: math.nan,
        }
    )

    with pytest.raises(
        ValueError,
        match="must be finite",
    ):

        monitor.monitor(trade)


@pytest.mark.parametrize(
    "field",
    [
        "entry_price",
        "current_price",
        "stop_loss",
    ],
)
def test_infinite_price_is_rejected(
    monitor,
    field,
):

    trade = make_trade(
        **{
            field: math.inf,
        }
    )

    with pytest.raises(
        ValueError,
        match="must be finite",
    ):

        monitor.monitor(trade)


def test_invalid_drawdown_guard_dependency():

    with pytest.raises(
        TypeError,
    ):

        InTradeMonitor(
            drawdown_guard=None,
            kill_switch=KillSwitch(),
        )


def test_invalid_kill_switch_dependency():

    with pytest.raises(
        TypeError,
    ):

        InTradeMonitor(
            drawdown_guard=DrawdownGuard(),
            kill_switch=None,
        )


def test_recovery_does_not_activate_kill_switch(
    monitor,
    kill_switch,
):

    trade = make_trade(
        current_balance=12_000.0,
    )

    assert monitor.monitor(
        trade
    ) is True

    assert kill_switch.active is False


def test_result_type_is_boolean(
    monitor,
):

    result = monitor.monitor(
        make_trade()
    )

    assert isinstance(
        result,
        bool,
    )