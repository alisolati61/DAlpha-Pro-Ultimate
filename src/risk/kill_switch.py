"""Emergency trading kill switch with immutable state snapshots.

The kill switch blocks new trading activity after activation. It does not
close positions or submit orders; those actions belong to the execution and
position-management layers.

Activation is explicit and deactivation is never automatic.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

Clock = Callable[[], datetime]


@dataclass(frozen=True, slots=True)
class KillSwitchState:
    """Immutable snapshot of kill-switch state."""

    active: bool = False
    reason: str = ""
    activated_at: datetime | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.active, bool):
            raise TypeError("active must be a bool")

        if not isinstance(self.reason, str):
            raise TypeError("reason must be a string")

        normalized_reason = self.reason.strip()

        if self.active:
            if not normalized_reason:
                raise ValueError(
                    "reason must not be empty when active"
                )

            if self.activated_at is None:
                raise ValueError(
                    "activated_at is required when active"
                )

            activated_at = _normalize_utc_datetime(
                "activated_at",
                self.activated_at,
            )
        else:
            if normalized_reason:
                raise ValueError(
                    "reason must be empty when inactive"
                )

            if self.activated_at is not None:
                raise ValueError(
                    "activated_at must be None when inactive"
                )

            activated_at = None

        object.__setattr__(
            self,
            "reason",
            normalized_reason,
        )
        object.__setattr__(
            self,
            "activated_at",
            activated_at,
        )


class KillSwitch:
    """Explicit emergency stop for new trading activity."""

    DEFAULT_REASON = "Manual activation"

    __slots__ = (
        "_clock",
        "_state",
    )

    def __init__(
        self,
        *,
        clock: Clock | None = None,
    ) -> None:
        if clock is not None and not callable(clock):
            raise TypeError(
                "clock must be callable or None"
            )

        self._clock: Clock = (
            _utc_now
            if clock is None
            else clock
        )
        self._state = KillSwitchState()

    @property
    def state(self) -> KillSwitchState:
        """Return the current immutable state snapshot."""

        return self._state

    @property
    def active(self) -> bool:
        """Return whether new trading activity must be blocked."""

        return self._state.active

    @property
    def reason(self) -> str:
        """Return the normalized activation reason."""

        return self._state.reason

    @property
    def activated_at(self) -> datetime | None:
        """Return the UTC activation time, if active."""

        return self._state.activated_at

    def is_active(self) -> bool:
        """Backward-compatible active-state query."""

        return self.active

    def activate(
        self,
        reason: str = DEFAULT_REASON,
    ) -> None:
        """Activate or reactivate the kill switch.

        Reactivation replaces the previous reason and timestamp with a new
        immutable state snapshot.
        """

        if not isinstance(reason, str):
            raise TypeError(
                "Reason must be a string."
            )

        normalized_reason = reason.strip()

        if not normalized_reason:
            raise ValueError(
                "Reason cannot be empty."
            )

        activated_at = _normalize_utc_datetime(
            "clock result",
            self._clock(),
        )

        self._state = KillSwitchState(
            active=True,
            reason=normalized_reason,
            activated_at=activated_at,
        )

    def deactivate(self) -> None:
        """Explicitly reset the kill switch to its inactive state."""

        self._state = KillSwitchState()


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _normalize_utc_datetime(
    name: str,
    value: object,
) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError(
            f"{name} must be a datetime"
        )

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(
            f"{name} must be timezone-aware"
        )

    return value.astimezone(UTC)


__all__ = (
    "Clock",
    "KillSwitch",
    "KillSwitchState",
)