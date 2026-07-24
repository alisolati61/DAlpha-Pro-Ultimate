"""Active risk monitoring for an open trade.

The monitor applies controls in deterministic order:

1. An already-active kill switch blocks immediately.
2. Trade data is validated.
3. Portfolio drawdown is evaluated.
4. A drawdown breach activates the kill switch.
5. The trade stop loss is evaluated.
6. Otherwise, the trade may continue.

The monitor never closes a position and never submits an order. It only
returns a risk decision for the execution or position-management layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite
from numbers import Real

from src.risk.drawdown_guard import (
    DrawdownGuard,
)
from src.risk.kill_switch import KillSwitch


class TradeDirection(str, Enum):
    """Supported trade directions."""

    LONG = "LONG"
    SHORT = "SHORT"


class InTradeDecision(str, Enum):
    """Possible in-trade risk decisions."""

    CONTINUE = "CONTINUE"
    KILL_SWITCH = "KILL_SWITCH"
    DRAWDOWN_BREACH = "DRAWDOWN_BREACH"
    STOP_LOSS = "STOP_LOSS"


@dataclass(frozen=True, slots=True)
class TradeState:
    """Immutable market and account snapshot for an open trade.

    ``direction`` is optional for backward compatibility. When omitted, the
    monitor infers direction from the initial stop-loss placement:

    - stop loss below entry: long;
    - stop loss above entry: short.

    Explicit direction should be supplied after a trailing stop crosses the
    entry price, because direction can no longer be inferred safely.
    """

    entry_price: float
    current_price: float
    stop_loss: float
    peak_balance: float
    current_balance: float
    direction: TradeDirection | str | None = None


@dataclass(frozen=True, slots=True)
class TradeMonitorResult:
    """Immutable result of one in-trade risk evaluation."""

    allowed: bool
    decision: InTradeDecision
    reason: str = ""
    drawdown: float | None = None
    direction: TradeDirection | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.allowed, bool):
            raise TypeError(
                "allowed must be a bool"
            )

        if not isinstance(
            self.decision,
            InTradeDecision,
        ):
            raise TypeError(
                "decision must be an InTradeDecision"
            )

        if not isinstance(self.reason, str):
            raise TypeError(
                "reason must be a string"
            )

        reason = self.reason.strip()

        if self.drawdown is None:
            drawdown = None
        else:
            drawdown = _validate_ratio(
                self.drawdown,
                "drawdown",
            )

        if (
            self.direction is not None
            and not isinstance(
                self.direction,
                TradeDirection,
            )
        ):
            raise TypeError(
                "direction must be a TradeDirection or None"
            )

        if self.decision is InTradeDecision.CONTINUE:
            if not self.allowed:
                raise ValueError(
                    "CONTINUE decision must be allowed"
                )

            if reason:
                raise ValueError(
                    "CONTINUE decision must not have a reason"
                )
        else:
            if self.allowed:
                raise ValueError(
                    "blocking decision cannot be allowed"
                )

            if not reason:
                raise ValueError(
                    "blocking decision requires a reason"
                )

        object.__setattr__(
            self,
            "reason",
            reason,
        )
        object.__setattr__(
            self,
            "drawdown",
            drawdown,
        )

    @property
    def blocked(self) -> bool:
        """Return whether continuation was rejected."""

        return not self.allowed

    @property
    def stop_loss_hit(self) -> bool:
        """Return whether the decision was caused by the stop loss."""

        return (
            self.decision
            is InTradeDecision.STOP_LOSS
        )

    @property
    def drawdown_breached(self) -> bool:
        """Return whether the decision was caused by portfolio drawdown."""

        return (
            self.decision
            is InTradeDecision.DRAWDOWN_BREACH
        )


class InTradeMonitor:
    """Coordinate active risk controls for a single open trade."""

    DRAWDOWN_REASON = "Maximum drawdown exceeded"
    STOP_LOSS_REASON = "Stop loss reached."
    KILL_SWITCH_FALLBACK_REASON = (
        "Kill switch is active."
    )

    __slots__ = (
        "drawdown_guard",
        "kill_switch",
    )

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

    def evaluate(
        self,
        trade: TradeState,
    ) -> TradeMonitorResult:
        """Evaluate whether an open trade may continue."""

        if not isinstance(
            trade,
            TradeState,
        ):
            raise TypeError(
                "trade must be a TradeState."
            )

        if self.kill_switch.active:
            return TradeMonitorResult(
                allowed=False,
                decision=InTradeDecision.KILL_SWITCH,
                reason=(
                    self.kill_switch.reason
                    or self.KILL_SWITCH_FALLBACK_REASON
                ),
            )

        direction = self._validate_trade(
            trade,
        )

        drawdown_status = self.drawdown_guard.check(
            trade.peak_balance,
            trade.current_balance,
        )

        if not drawdown_status.allowed:
            if not self.kill_switch.active:
                self.kill_switch.activate(
                    self.DRAWDOWN_REASON
                )

            return TradeMonitorResult(
                allowed=False,
                decision=(
                    InTradeDecision.DRAWDOWN_BREACH
                ),
                reason=self.DRAWDOWN_REASON,
                drawdown=drawdown_status.drawdown,
                direction=direction,
            )

        if self._stop_loss_reached(
            trade,
            direction,
        ):
            return TradeMonitorResult(
                allowed=False,
                decision=InTradeDecision.STOP_LOSS,
                reason=self.STOP_LOSS_REASON,
                drawdown=drawdown_status.drawdown,
                direction=direction,
            )

        return TradeMonitorResult(
            allowed=True,
            decision=InTradeDecision.CONTINUE,
            drawdown=drawdown_status.drawdown,
            direction=direction,
        )

    def monitor(
        self,
        trade: TradeState,
    ) -> bool:
        """Backward-compatible boolean continuation check."""

        return self.evaluate(
            trade,
        ).allowed

    @classmethod
    def _validate_trade(
        cls,
        trade: TradeState,
    ) -> TradeDirection:
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

        return cls._resolve_direction(
            trade,
        )

    @staticmethod
    def _validate_price(
        value: object,
        name: str,
    ) -> float:
        if (
            isinstance(value, bool)
            or not isinstance(value, Real)
        ):
            raise TypeError(
                f"{name} must be a number."
            )

        price = float(value)

        if not isfinite(price):
            raise ValueError(
                f"{name} must be finite."
            )

        if price <= 0.0:
            raise ValueError(
                f"{name} must be greater than zero."
            )

        return price

    @classmethod
    def _resolve_direction(
        cls,
        trade: TradeState,
    ) -> TradeDirection:
        if trade.direction is not None:
            return cls._normalize_direction(
                trade.direction,
            )

        entry_price = float(
            trade.entry_price,
        )
        stop_loss = float(
            trade.stop_loss,
        )

        if stop_loss < entry_price:
            return TradeDirection.LONG

        if stop_loss > entry_price:
            return TradeDirection.SHORT

        raise ValueError(
            "direction cannot be inferred when "
            "stop_loss equals entry_price."
        )

    @staticmethod
    def _normalize_direction(
        value: object,
    ) -> TradeDirection:
        if isinstance(
            value,
            TradeDirection,
        ):
            return value

        if not isinstance(value, str):
            raise TypeError(
                "direction must be a TradeDirection, "
                "string, or None."
            )

        normalized = value.strip().upper()

        try:
            return TradeDirection(
                normalized,
            )
        except ValueError as error:
            raise ValueError(
                "direction must be LONG or SHORT."
            ) from error

    @staticmethod
    def _stop_loss_reached(
        trade: TradeState,
        direction: TradeDirection,
    ) -> bool:
        current_price = float(
            trade.current_price,
        )
        stop_loss = float(
            trade.stop_loss,
        )

        if direction is TradeDirection.LONG:
            return current_price <= stop_loss

        return current_price >= stop_loss


def _validate_ratio(
    value: object,
    name: str,
) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, Real)
    ):
        raise TypeError(
            f"{name} must be a number"
        )

    ratio = float(value)

    if not isfinite(ratio):
        raise ValueError(
            f"{name} must be finite"
        )

    if not 0.0 <= ratio <= 1.0:
        raise ValueError(
            f"{name} must be between 0 and 1"
        )

    return ratio


__all__ = (
    "InTradeDecision",
    "InTradeMonitor",
    "TradeDirection",
    "TradeMonitorResult",
    "TradeState",
)