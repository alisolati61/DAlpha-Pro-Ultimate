from src.risk.drawdown_guard import DrawdownGuard
from src.risk.kill_switch import KillSwitch
from src.risk.in_trade_monitor import (
    InTradeMonitor,
    TradeState,
)


def test_trade_allowed():

    monitor = InTradeMonitor(
        DrawdownGuard(0.15),
        KillSwitch(),
    )

    trade = TradeState(
        entry_price=100,
        current_price=110,
        stop_loss=95,
        peak_balance=10000,
        current_balance=9800,
    )

    assert monitor.monitor(trade)


def test_trade_blocked():

    monitor = InTradeMonitor(
        DrawdownGuard(0.05),
        KillSwitch(),
    )

    trade = TradeState(
        entry_price=100,
        current_price=90,
        stop_loss=95,
        peak_balance=10000,
        current_balance=9000,
    )

    assert not monitor.monitor(trade)