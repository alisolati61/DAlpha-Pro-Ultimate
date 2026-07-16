from __future__ import annotations

from dataclasses import dataclass

from src.risk.drawdown_guard import DrawdownGuard
from src.risk.kill_switch import KillSwitch


@dataclass(slots=True)
class TradeState:
    entry_price: float
    current_price: float
    stop_loss: float
    peak_balance: float
    current_balance: float


class InTradeMonitor:
    """
    Monitors an open trade and triggers
    risk controls when necessary.
    """

    def __init__(
        self,
        drawdown_guard: DrawdownGuard,
        kill_switch: KillSwitch,
    ) -> None:

        self.drawdown_guard = drawdown_guard
        self.kill_switch = kill_switch

    def monitor(
        self,
        trade: TradeState,
    ) -> bool:

        if not self.drawdown_guard.can_continue(
            trade.peak_balance,
            trade.current_balance,
        ):
            self.kill_switch.activate("Maximum drawdown exceeded")
            return False

        if self.kill_switch.active:
            return False

        return True