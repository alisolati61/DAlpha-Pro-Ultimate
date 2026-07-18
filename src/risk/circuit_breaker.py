from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta


@dataclass(frozen=True, slots=True)
class CircuitBreakerState:
    active: bool = False
    reason: str = ""
    activated_at: datetime | None = None


class CircuitBreaker:
    """
    Stops trading after predefined risk conditions are reached.

    A circuit breaker activates after a configured number of
    consecutive losing trades.

    Profit semantics:

        profit < 0
            losing trade

        profit >= 0
            non-losing trade

    A cooldown period prevents trading while the breaker is active.
    """

    def __init__(
        self,
        max_consecutive_losses: int = 5,
        cooldown_minutes: int = 30,
    ) -> None:

        if not isinstance(
            max_consecutive_losses,
            int,
        ):

            raise TypeError(
                "max_consecutive_losses must be an integer."
            )

        if max_consecutive_losses <= 0:

            raise ValueError(
                "max_consecutive_losses must be greater than zero."
            )

        if not isinstance(
            cooldown_minutes,
            int,
        ):

            raise TypeError(
                "cooldown_minutes must be an integer."
            )

        if cooldown_minutes < 0:

            raise ValueError(
                "cooldown_minutes cannot be negative."
            )

        self.max_consecutive_losses = (
            max_consecutive_losses
        )

        self.cooldown = timedelta(
            minutes=cooldown_minutes
        )

        self.loss_counter = 0

        self.state = CircuitBreakerState()

    # --------------------------------------------------

    @staticmethod
    def _validate_profit(
        profit: float,
    ) -> None:

        if not isinstance(
            profit,
            (int, float),
        ):

            raise TypeError(
                "Profit must be a number."
            )

        if not math.isfinite(profit):

            raise ValueError(
                "Profit must be finite."
            )

    # --------------------------------------------------

    def register_trade(
        self,
        profit: float,
    ) -> None:

        self._validate_profit(
            profit
        )

        if profit < 0:

            self.loss_counter += 1

        else:

            self.loss_counter = 0

        if (

            self.loss_counter
            >= self.max_consecutive_losses

        ):

            self.activate(
                "Maximum consecutive losses reached."
            )

    # --------------------------------------------------

    def activate(
        self,
        reason: str,
    ) -> None:

        if not isinstance(
            reason,
            str,
        ):

            raise TypeError(
                "Reason must be a string."
            )

        reason = reason.strip()

        if not reason:

            raise ValueError(
                "Reason cannot be empty."
            )

        self.state = CircuitBreakerState(

            active=True,

            reason=reason,

            activated_at=datetime.now(UTC),

        )

    # --------------------------------------------------

    def deactivate(self) -> None:

        self.loss_counter = 0

        self.state = CircuitBreakerState()

    # --------------------------------------------------

    def can_trade(self) -> bool:

        if not self.state.active:

            return True

        activated_at = (
            self.state.activated_at
        )

        if activated_at is None:

            return False

        now = datetime.now(UTC)

        if now >= (
            activated_at
            + self.cooldown
        ):

            self.deactivate()

            return True

        return False