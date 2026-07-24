"""Tests for active open-trade risk monitoring."""

from dataclasses import FrozenInstanceError
from math import inf, nan

import pytest

from src.risk.drawdown_guard import DrawdownGuard
from src.risk.in_trade_monitor import (
    InTradeDecision,
    InTradeMonitor,
    TradeDirection,
    TradeMonitorResult,
    TradeState,
)
from src.risk.kill_switch import KillSwitch


@pytest.fixture
def drawdown_guard() -> DrawdownGuard:
    return DrawdownGuard(
        max_drawdown=0.15,
    )


@pytest.fixture
def kill_switch() -> KillSwitch:
    return KillSwitch()


@pytest.fixture
def monitor(
    drawdown_guard: DrawdownGuard,
    kill_switch: KillSwitch,
) -> InTradeMonitor:
    return InTradeMonitor(
        drawdown_guard=drawdown_guard,
        kill_switch=kill_switch,
    )


def make_trade(
    **overrides: object,
) -> TradeState:
    data: dict[str, object] = {
        "entry_price": 100.0,
        "current_price": 105.0,
        "stop_loss": 95.0,
        "peak_balance": 10_000.0,
        "current_balance": 9_500.0,
    }
    data.update(overrides)

    return TradeState(
        **data,  # type: ignore[arg-type]
    )


def test_trade_can_continue_when_risk_is_valid(
    monitor: InTradeMonitor,
) -> None:
    assert monitor.monitor(
        make_trade()
    ) is True


def test_evaluate_returns_continue_result(
    monitor: InTradeMonitor,
) -> None:
    result = monitor.evaluate(
        make_trade()
    )

    assert result == TradeMonitorResult(
        allowed=True,
        decision=InTradeDecision.CONTINUE,
        drawdown=0.05,
        direction=TradeDirection.LONG,
    )
    assert result.blocked is False


def test_monitor_result_type_is_boolean(
    monitor: InTradeMonitor,
) -> None:
    result = monitor.monitor(
        make_trade()
    )

    assert type(result) is bool


def test_active_kill_switch_blocks_trade(
    monitor: InTradeMonitor,
    kill_switch: KillSwitch,
) -> None:
    kill_switch.activate(
        "Manual emergency stop"
    )

    result = monitor.evaluate(
        make_trade()
    )

    assert result.allowed is False
    assert (
        result.decision
        is InTradeDecision.KILL_SWITCH
    )
    assert result.reason == "Manual emergency stop"
    assert result.drawdown is None
    assert result.direction is None


def test_active_kill_switch_has_first_priority(
    monitor: InTradeMonitor,
    kill_switch: KillSwitch,
) -> None:
    kill_switch.activate(
        "Manual emergency stop"
    )

    invalid_trade = make_trade(
        entry_price=nan,
        current_balance=-1,
    )

    result = monitor.evaluate(
        invalid_trade
    )

    assert (
        result.decision
        is InTradeDecision.KILL_SWITCH
    )


def test_drawdown_breach_blocks_trade(
    monitor: InTradeMonitor,
    kill_switch: KillSwitch,
) -> None:
    result = monitor.evaluate(
        make_trade(
            current_balance=8_500.0,
        )
    )

    assert result.allowed is False
    assert (
        result.decision
        is InTradeDecision.DRAWDOWN_BREACH
    )
    assert result.drawdown == 0.15
    assert result.drawdown_breached is True
    assert kill_switch.active is True
    assert (
        kill_switch.reason
        == "Maximum drawdown exceeded"
    )


def test_drawdown_above_limit_activates_kill_switch(
    monitor: InTradeMonitor,
    kill_switch: KillSwitch,
) -> None:
    assert kill_switch.active is False

    monitor.monitor(
        make_trade(
            current_balance=8_000.0,
        )
    )

    assert kill_switch.active is True


def test_drawdown_at_exact_limit_is_blocked(
    monitor: InTradeMonitor,
) -> None:
    assert monitor.monitor(
        make_trade(
            current_balance=8_500.0,
        )
    ) is False


def test_drawdown_below_limit_is_allowed(
    monitor: InTradeMonitor,
    kill_switch: KillSwitch,
) -> None:
    assert monitor.monitor(
        make_trade(
            current_balance=8_501.0,
        )
    ) is True
    assert kill_switch.active is False


def test_drawdown_has_priority_over_stop_loss(
    monitor: InTradeMonitor,
    kill_switch: KillSwitch,
) -> None:
    result = monitor.evaluate(
        make_trade(
            current_price=90.0,
            current_balance=8_000.0,
        )
    )

    assert (
        result.decision
        is InTradeDecision.DRAWDOWN_BREACH
    )
    assert kill_switch.active is True


def test_recovery_does_not_activate_kill_switch(
    monitor: InTradeMonitor,
    kill_switch: KillSwitch,
) -> None:
    assert monitor.monitor(
        make_trade(
            current_balance=12_000.0,
        )
    ) is True
    assert kill_switch.active is False


def test_long_stop_loss_below_boundary_is_hit(
    monitor: InTradeMonitor,
) -> None:
    result = monitor.evaluate(
        make_trade(
            current_price=94.99,
        )
    )

    assert result.allowed is False
    assert (
        result.decision
        is InTradeDecision.STOP_LOSS
    )
    assert result.reason == "Stop loss reached."
    assert result.stop_loss_hit is True
    assert result.direction is TradeDirection.LONG


def test_long_stop_loss_at_exact_boundary_is_hit(
    monitor: InTradeMonitor,
) -> None:
    result = monitor.evaluate(
        make_trade(
            current_price=95.0,
        )
    )

    assert (
        result.decision
        is InTradeDecision.STOP_LOSS
    )


def test_long_trade_above_stop_continues(
    monitor: InTradeMonitor,
) -> None:
    result = monitor.evaluate(
        make_trade(
            current_price=95.01,
        )
    )

    assert (
        result.decision
        is InTradeDecision.CONTINUE
    )


def test_short_direction_is_inferred(
    monitor: InTradeMonitor,
) -> None:
    result = monitor.evaluate(
        make_trade(
            current_price=95.0,
            stop_loss=105.0,
        )
    )

    assert result.allowed is True
    assert result.direction is TradeDirection.SHORT


def test_short_stop_loss_above_boundary_is_hit(
    monitor: InTradeMonitor,
) -> None:
    result = monitor.evaluate(
        make_trade(
            current_price=105.01,
            stop_loss=105.0,
        )
    )

    assert (
        result.decision
        is InTradeDecision.STOP_LOSS
    )
    assert result.direction is TradeDirection.SHORT


def test_short_stop_loss_at_exact_boundary_is_hit(
    monitor: InTradeMonitor,
) -> None:
    result = monitor.evaluate(
        make_trade(
            current_price=105.0,
            stop_loss=105.0,
        )
    )

    assert (
        result.decision
        is InTradeDecision.STOP_LOSS
    )


@pytest.mark.parametrize(
    ("direction", "expected"),
    [
        (
            TradeDirection.LONG,
            TradeDirection.LONG,
        ),
        (
            TradeDirection.SHORT,
            TradeDirection.SHORT,
        ),
        (
            "long",
            TradeDirection.LONG,
        ),
        (
            " LONG ",
            TradeDirection.LONG,
        ),
        (
            "short",
            TradeDirection.SHORT,
        ),
        (
            " SHORT ",
            TradeDirection.SHORT,
        ),
    ],
)
def test_explicit_direction_is_normalized(
    monitor: InTradeMonitor,
    direction: TradeDirection | str,
    expected: TradeDirection,
) -> None:
    result = monitor.evaluate(
        make_trade(
            direction=direction,
        )
    )

    assert result.direction is expected


def test_explicit_long_supports_trailing_stop_above_entry(
    monitor: InTradeMonitor,
) -> None:
    result = monitor.evaluate(
        make_trade(
            current_price=108.0,
            stop_loss=105.0,
            direction=TradeDirection.LONG,
        )
    )

    assert result.allowed is True
    assert result.direction is TradeDirection.LONG


def test_explicit_long_trailing_stop_is_enforced(
    monitor: InTradeMonitor,
) -> None:
    result = monitor.evaluate(
        make_trade(
            current_price=104.0,
            stop_loss=105.0,
            direction=TradeDirection.LONG,
        )
    )

    assert (
        result.decision
        is InTradeDecision.STOP_LOSS
    )


def test_explicit_short_supports_stop_below_entry(
    monitor: InTradeMonitor,
) -> None:
    result = monitor.evaluate(
        make_trade(
            current_price=92.0,
            stop_loss=95.0,
            direction=TradeDirection.SHORT,
        )
    )

    assert result.allowed is True
    assert result.direction is TradeDirection.SHORT


def test_equal_entry_and_stop_requires_explicit_direction(
    monitor: InTradeMonitor,
) -> None:
    with pytest.raises(
        ValueError,
        match="direction cannot be inferred",
    ):
        monitor.monitor(
            make_trade(
                stop_loss=100.0,
            )
        )


def test_equal_entry_and_stop_is_valid_with_direction(
    monitor: InTradeMonitor,
) -> None:
    result = monitor.evaluate(
        make_trade(
            current_price=101.0,
            stop_loss=100.0,
            direction="LONG",
        )
    )

    assert result.allowed is True


@pytest.mark.parametrize(
    "direction",
    [
        "",
        " ",
        "BUY",
        "SELL",
        "UP",
        "DOWN",
    ],
)
def test_invalid_direction_value_is_rejected(
    monitor: InTradeMonitor,
    direction: str,
) -> None:
    with pytest.raises(
        ValueError,
        match="direction must be LONG or SHORT",
    ):
        monitor.monitor(
            make_trade(
                direction=direction,
            )
        )


@pytest.mark.parametrize(
    "direction",
    [
        1,
        True,
        object(),
    ],
)
def test_invalid_direction_type_is_rejected(
    monitor: InTradeMonitor,
    direction: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="direction must be",
    ):
        monitor.monitor(
            make_trade(
                direction=direction,
            )
        )


def test_existing_kill_switch_reason_is_preserved(
    monitor: InTradeMonitor,
    kill_switch: KillSwitch,
) -> None:
    kill_switch.activate(
        "Manual emergency stop"
    )

    assert monitor.monitor(
        make_trade(
            current_balance=8_000.0,
        )
    ) is False

    assert (
        kill_switch.reason
        == "Manual emergency stop"
    )


def test_stop_loss_does_not_activate_kill_switch(
    monitor: InTradeMonitor,
    kill_switch: KillSwitch,
) -> None:
    result = monitor.evaluate(
        make_trade(
            current_price=90.0,
        )
    )

    assert (
        result.decision
        is InTradeDecision.STOP_LOSS
    )
    assert kill_switch.active is False


def test_trade_state_is_immutable() -> None:
    trade = make_trade()

    with pytest.raises(
        FrozenInstanceError,
    ):
        trade.current_price = 200.0  # type: ignore[misc]


def test_invalid_trade_type_is_rejected(
    monitor: InTradeMonitor,
) -> None:
    with pytest.raises(
        TypeError,
        match="trade must be a TradeState",
    ):
        monitor.monitor(
            None,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "field",
    [
        "entry_price",
        "current_price",
        "stop_loss",
    ],
)
@pytest.mark.parametrize(
    "value",
    [
        0,
        -1,
    ],
)
def test_non_positive_price_is_rejected(
    monitor: InTradeMonitor,
    field: str,
    value: float,
) -> None:
    with pytest.raises(
        ValueError,
        match="greater than zero",
    ):
        monitor.monitor(
            make_trade(
                **{
                    field: value,
                }
            )
        )


@pytest.mark.parametrize(
    "field",
    [
        "entry_price",
        "current_price",
        "stop_loss",
    ],
)
@pytest.mark.parametrize(
    "value",
    [
        nan,
        inf,
        -inf,
    ],
)
def test_non_finite_price_is_rejected(
    monitor: InTradeMonitor,
    field: str,
    value: float,
) -> None:
    with pytest.raises(
        ValueError,
        match="must be finite",
    ):
        monitor.monitor(
            make_trade(
                **{
                    field: value,
                }
            )
        )


@pytest.mark.parametrize(
    "field",
    [
        "entry_price",
        "current_price",
        "stop_loss",
    ],
)
@pytest.mark.parametrize(
    "value",
    [
        True,
        False,
        "100",
        None,
        object(),
    ],
)
def test_non_numeric_price_is_rejected(
    monitor: InTradeMonitor,
    field: str,
    value: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="must be a number",
    ):
        monitor.monitor(
            make_trade(
                **{
                    field: value,
                }
            )
        )


def test_invalid_peak_balance_is_delegated_to_guard(
    monitor: InTradeMonitor,
) -> None:
    with pytest.raises(
        ValueError,
        match="Peak balance must be greater than zero",
    ):
        monitor.monitor(
            make_trade(
                peak_balance=0,
            )
        )


def test_invalid_current_balance_is_delegated_to_guard(
    monitor: InTradeMonitor,
) -> None:
    with pytest.raises(
        ValueError,
        match="current_balance cannot be negative",
    ):
        monitor.monitor(
            make_trade(
                current_balance=-1,
            )
        )


def test_invalid_drawdown_guard_dependency() -> None:
    with pytest.raises(
        TypeError,
        match=(
            "drawdown_guard must be "
            "a DrawdownGuard"
        ),
    ):
        InTradeMonitor(
            drawdown_guard=None,  # type: ignore[arg-type]
            kill_switch=KillSwitch(),
        )


def test_invalid_kill_switch_dependency() -> None:
    with pytest.raises(
        TypeError,
        match=(
            "kill_switch must be "
            "a KillSwitch"
        ),
    ):
        InTradeMonitor(
            drawdown_guard=DrawdownGuard(),
            kill_switch=None,  # type: ignore[arg-type]
        )


def test_result_is_immutable(
    monitor: InTradeMonitor,
) -> None:
    result = monitor.evaluate(
        make_trade()
    )

    with pytest.raises(
        FrozenInstanceError,
    ):
        result.allowed = False  # type: ignore[misc]


def test_result_strips_reason() -> None:
    result = TradeMonitorResult(
        allowed=False,
        decision=InTradeDecision.STOP_LOSS,
        reason="  Stop loss reached.  ",
    )

    assert result.reason == "Stop loss reached."


@pytest.mark.parametrize(
    "allowed",
    [
        1,
        "True",
        None,
    ],
)
def test_result_rejects_non_boolean_allowed(
    allowed: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="allowed must be a bool",
    ):
        TradeMonitorResult(
            allowed=allowed,  # type: ignore[arg-type]
            decision=InTradeDecision.CONTINUE,
        )


def test_result_rejects_invalid_decision_type() -> None:
    with pytest.raises(
        TypeError,
        match=(
            "decision must be "
            "an InTradeDecision"
        ),
    ):
        TradeMonitorResult(
            allowed=True,
            decision="CONTINUE",  # type: ignore[arg-type]
        )


def test_continue_result_must_be_allowed() -> None:
    with pytest.raises(
        ValueError,
        match="CONTINUE decision must be allowed",
    ):
        TradeMonitorResult(
            allowed=False,
            decision=InTradeDecision.CONTINUE,
        )


def test_continue_result_rejects_reason() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "CONTINUE decision must not "
            "have a reason"
        ),
    ):
        TradeMonitorResult(
            allowed=True,
            decision=InTradeDecision.CONTINUE,
            reason="Not valid",
        )


def test_blocking_result_cannot_be_allowed() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "blocking decision cannot "
            "be allowed"
        ),
    ):
        TradeMonitorResult(
            allowed=True,
            decision=InTradeDecision.STOP_LOSS,
            reason="Stop",
        )


def test_blocking_result_requires_reason() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "blocking decision requires "
            "a reason"
        ),
    ):
        TradeMonitorResult(
            allowed=False,
            decision=InTradeDecision.STOP_LOSS,
        )


@pytest.mark.parametrize(
    "reason",
    [
        None,
        1,
        True,
    ],
)
def test_result_rejects_non_string_reason(
    reason: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="reason must be a string",
    ):
        TradeMonitorResult(
            allowed=False,
            decision=InTradeDecision.STOP_LOSS,
            reason=reason,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "drawdown",
    [
        -0.01,
        1.01,
        nan,
        inf,
        -inf,
    ],
)
def test_result_rejects_invalid_drawdown(
    drawdown: float,
) -> None:
    with pytest.raises(ValueError):
        TradeMonitorResult(
            allowed=False,
            decision=(
                InTradeDecision.DRAWDOWN_BREACH
            ),
            reason="Drawdown",
            drawdown=drawdown,
        )


@pytest.mark.parametrize(
    "drawdown",
    [
        True,
        "0.1",
        object(),
    ],
)
def test_result_rejects_non_numeric_drawdown(
    drawdown: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="drawdown must be a number",
    ):
        TradeMonitorResult(
            allowed=False,
            decision=(
                InTradeDecision.DRAWDOWN_BREACH
            ),
            reason="Drawdown",
            drawdown=drawdown,  # type: ignore[arg-type]
        )


def test_result_rejects_invalid_direction() -> None:
    with pytest.raises(
        TypeError,
        match=(
            "direction must be a "
            "TradeDirection or None"
        ),
    ):
        TradeMonitorResult(
            allowed=True,
            decision=InTradeDecision.CONTINUE,
            direction="LONG",  # type: ignore[arg-type]
        )