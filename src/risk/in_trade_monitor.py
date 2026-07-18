from __future__ import annotations

import math
from dataclasses import dataclass

from src.risk.drawdown_guard import DrawdownGuard
from src.risk.kill_switch import KillSwitch


@dataclass(frozen=True, slots=True)
class TradeState:
    entry_price: float
    current_price: float
    stop_loss: float
    peak_balance: float
    current_balance: float


class InTradeMonitor:
    """
    Monitors an open trade and enforces active risk controls.

    The monitor follows this priority:

    1. An already-active KillSwitch blocks trading immediately.
    2. Portfolio drawdown is checked.
    3. If drawdown breaches the limit, the KillSwitch is activated.
    4. Otherwise, the trade may continue.

    This class does not close positions directly.
    Position closing belongs to the execution/position-management layer.
    """

    DRAWDOWN_REASON = "Maximum drawdown exceeded"

    def __init__(
        self,
        drawdown_guard: DrawdownGuard,
        kill_switch: KillSwitch,
    ) -> None:

        if not isinstance(
            drawdown_guard,
            DrawdownGuard,
        ):

            raise TypeError(
                "drawdown_guard must be a DrawdownGuard."
            )

        if not isinstance(
            kill_switch,
            KillSwitch,
        ):

            raise TypeError(
                "kill_switch must be a KillSwitch."
            )

        self.drawdown_guard = drawdown_guard
        self.kill_switch = kill_switch

    # --------------------------------------------------

    @staticmethod
    def _validate_price(
        value: float,
        name: str,
    ) -> None:

        if not isinstance(
            value,
            (int, float),
        ):

            raise TypeError(
                f"{name} must be a number."
            )

        if not math.isfinite(value):

            raise ValueError(
                f"{name} must be finite."
            )

        if value <= 0:

            raise ValueError(
                f"{name} must be greater than zero."
            )

    # --------------------------------------------------

    @classmethod
    def _validate_trade(
        cls,
        trade: TradeState,
    ) -> None:

        if not isinstance(
            trade,
            TradeState,
        ):

            raise TypeError(
                "trade must be a TradeState."
            )

        cls._validate_price(
            trade.entry_price,
            "entry_price",
        )

        cls._validate_price(
            trade.current_price,
            "current_price",
        )

        cls._validate_price(
            trade.stop_loss,
            "stop_loss",
        )

    # --------------------------------------------------

    def monitor(
        self,
        trade: TradeState,
    ) -> bool:

        self._validate_trade(
            trade
        )

        if self.kill_switch.active:

            return False

        if not self.drawdown_guard.can_continue(
            trade.peak_balance,
            trade.current_balance,
        ):

            if not self.kill_switch.active:

                self.kill_switch.activate(
                    self.DRAWDOWN_REASON
                )

            return False

        return True