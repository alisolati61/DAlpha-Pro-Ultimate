from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta


@dataclass(slots=True)
class CircuitBreakerState:
    active: bool = False
    reason: str = ""
    activated_at: datetime | None = None


class CircuitBreaker:
    """
    Stops all trading when predefined
    risk thresholds are exceeded.
    """

    def __init__(
        self,
        max_consecutive_losses: int = 5,
        cooldown_minutes: int = 30,
    ) -> None:

        self.max_consecutive_losses = max_consecutive_losses
        self.cooldown = timedelta(minutes=cooldown_minutes)

        self.loss_counter = 0

        self.state = CircuitBreakerState()

    def register_trade(self, profit: float) -> None:

        if profit < 0:
            self.loss_counter += 1
        else:
            self.loss_counter = 0

        if self.loss_counter >= self.max_consecutive_losses:
            self.activate(
                "Maximum consecutive losses reached."
            )

    def activate(self, reason: str) -> None:

        self.state.active = True
        self.state.reason = reason
        self.state.activated_at = datetime.now(UTC)

    def deactivate(self) -> None:

        self.loss_counter = 0
        self.state.active = False
        self.state.reason = ""
        self.state.activated_at = None

    def can_trade(self) -> bool:

        if not self.state.active:
            return True

        if self.state.activated_at is None:
            return False

        if datetime.now(UTC) >= (
            self.state.activated_at + self.cooldown
        ):
            self.deactivate()
            return True

        return False