"""Consecutive-loss circuit breaker for the trading risk layer.

The breaker blocks new trading activity after a configured number of
consecutive losing trades. A non-losing trade resets the loss counter.

While active, ``can_trade()`` remains false until the cooldown expires. Once
the cooldown has elapsed, the breaker automatically deactivates and resets its
loss counter.

Profit semantics:
- ``profit < 0``: losing trade;
- ``profit >= 0``: non-losing trade.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from math import isfinite
from numbers import Real

Clock = Callable[[], datetime]

_MAX_REASON_LENGTH = 500


@dataclass(frozen=True, slots=True)
class CircuitBreakerState:
    """Immutable snapshot of circuit-breaker state.

    An active state may intentionally have no timestamp. This preserves the
    existing fail-closed contract: an active breaker with an unknown activation
    time blocks trading indefinitely until manually deactivated.
    """

    active: bool = False
    reason: str = ""
    activated_at: datetime | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.active, bool):
            raise TypeError("active must be a bool")

        if not isinstance(self.reason, str):
            raise TypeError("reason must be a string")

        reason = self.reason.strip()

        if len(reason) > _MAX_REASON_LENGTH:
            raise ValueError(
                f"reason must not exceed {_MAX_REASON_LENGTH} characters"
            )

        activated_at = self.activated_at

        if activated_at is not None:
            activated_at = _normalize_utc_datetime(
                "activated_at",
                activated_at,
            )

        if self.active:
            if not reason:
                raise ValueError(
                    "reason must not be empty when active"
                )
        else:
            if reason:
                raise ValueError(
                    "reason must be empty when inactive"
                )

            if activated_at is not None:
                raise ValueError(
                    "activated_at must be None when inactive"
                )

        object.__setattr__(
            self,
            "reason",
            reason,
        )
        object.__setattr__(
            self,
            "activated_at",
            activated_at,
        )


class CircuitBreaker:
    """Block trading after consecutive losses until cooldown completion."""

    DEFAULT_ACTIVATION_REASON = (
        "Maximum consecutive losses reached."
    )

    __slots__ = (
        "_clock",
        "cooldown",
        "loss_counter",
        "max_consecutive_losses",
        "state",
    )

    def __init__(
        self,
        max_consecutive_losses: int = 5,
        cooldown_minutes: int = 30,
        *,
        clock: Clock | None = None,
    ) -> None:
        self.max_consecutive_losses = _validate_positive_integer(
            "max_consecutive_losses",
            max_consecutive_losses,
        )

        validated_cooldown_minutes = _validate_non_negative_integer(
            "cooldown_minutes",
            cooldown_minutes,
        )

        if clock is not None and not callable(clock):
            raise TypeError(
                "clock must be callable or None"
            )

        self.cooldown = timedelta(
            minutes=validated_cooldown_minutes,
        )
        self.loss_counter = 0
        self.state = CircuitBreakerState()
        self._clock: Clock = (
            _utc_now
            if clock is None
            else clock
        )

    @property
    def active(self) -> bool:
        """Return whether the breaker is currently active."""

        return self.state.active

    @property
    def reason(self) -> str:
        """Return the normalized activation reason."""

        return self.state.reason

    @property
    def activated_at(self) -> datetime | None:
        """Return the UTC activation timestamp, if known."""

        return self.state.activated_at

    @property
    def cooldown_minutes(self) -> int:
        """Return the configured cooldown duration in whole minutes."""

        return int(
            self.cooldown.total_seconds()
            // 60
        )

    def register_trade(
        self,
        profit: float,
    ) -> None:
        """Register a completed trade and update consecutive-loss state."""

        validated_profit = _validate_profit(
            profit,
        )

        if validated_profit < 0.0:
            self.loss_counter += 1
        else:
            self.loss_counter = 0

        if (
            self.loss_counter
            >= self.max_consecutive_losses
        ):
            self.activate(
                self.DEFAULT_ACTIVATION_REASON,
            )

    def activate(
        self,
        reason: str,
    ) -> None:
        """Activate or reactivate the breaker with a fresh UTC timestamp."""

        normalized_reason = _validate_reason(
            reason,
        )

        activated_at = _normalize_utc_datetime(
            "clock result",
            self._clock(),
        )

        self.state = CircuitBreakerState(
            active=True,
            reason=normalized_reason,
            activated_at=activated_at,
        )

    def deactivate(self) -> None:
        """Explicitly reset the breaker and consecutive-loss counter."""

        self.loss_counter = 0
        self.state = CircuitBreakerState()

    def can_trade(self) -> bool:
        """Return whether trading is permitted at the current clock time.

        The method automatically deactivates an active breaker once its
        cooldown has fully elapsed. An active state without an activation
        timestamp fails closed and continues blocking trading.
        """

        if not self.state.active:
            return True

        activated_at = self.state.activated_at

        if activated_at is None:
            return False

        now = _normalize_utc_datetime(
            "clock result",
            self._clock(),
        )

        if now >= activated_at + self.cooldown:
            self.deactivate()
            return True

        return False

    def cooldown_remaining(self) -> timedelta | None:
        """Return remaining cooldown without changing breaker state.

        ``None`` means the breaker is inactive. An active state without a
        timestamp returns the full configured cooldown because its elapsed
        duration cannot be determined.
        """

        if not self.state.active:
            return None

        activated_at = self.state.activated_at

        if activated_at is None:
            return self.cooldown

        now = _normalize_utc_datetime(
            "clock result",
            self._clock(),
        )

        remaining = (
            activated_at
            + self.cooldown
            - now
        )

        if remaining <= timedelta(0):
            return timedelta(0)

        return remaining


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _validate_profit(
    value: object,
) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, Real)
    ):
        raise TypeError(
            "Profit must be a number."
        )

    profit = float(value)

    if not isfinite(profit):
        raise ValueError(
            "Profit must be finite."
        )

    return profit


def _validate_reason(
    value: object,
) -> str:
    if not isinstance(value, str):
        raise TypeError(
            "Reason must be a string."
        )

    reason = value.strip()

    if not reason:
        raise ValueError(
            "Reason cannot be empty."
        )

    if len(reason) > _MAX_REASON_LENGTH:
        raise ValueError(
            f"Reason must not exceed {_MAX_REASON_LENGTH} characters."
        )

    return reason


def _validate_positive_integer(
    name: str,
    value: object,
) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
    ):
        raise TypeError(
            f"{name} must be an integer."
        )

    if value <= 0:
        raise ValueError(
            f"{name} must be greater than zero."
        )

    return value


def _validate_non_negative_integer(
    name: str,
    value: object,
) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
    ):
        raise TypeError(
            f"{name} must be an integer."
        )

    if value < 0:
        raise ValueError(
            f"{name} cannot be negative."
        )

    return value


def _normalize_utc_datetime(
    name: str,
    value: object,
) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError(
            f"{name} must be a datetime"
        )

    if (
        value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(
            f"{name} must be timezone-aware"
        )

    return value.astimezone(UTC)


__all__ = (
    "CircuitBreaker",
    "CircuitBreakerState",
    "Clock",
)