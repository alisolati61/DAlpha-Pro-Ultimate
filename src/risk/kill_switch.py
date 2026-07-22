from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True, slots=True)
class KillSwitchState:
    active: bool = False
    reason: str = ""
    activated_at: datetime | None = None


class KillSwitch:
    """
    Emergency trading stop.

    When activated:

    - No new positions are allowed.
    - Existing positions should be handled by the
      execution/position management layer.

    The kill switch is intentionally explicit and
    does not automatically deactivate.
    """

    DEFAULT_REASON = "Manual activation"

    def __init__(self) -> None:
        self._state = KillSwitchState()

    # --------------------------------------------------
    # State
    # --------------------------------------------------

    @property
    def state(self) -> KillSwitchState:
        return self._state

    @property
    def active(self) -> bool:
        return self._state.active

    @property
    def reason(self) -> str:
        return self._state.reason

    @property
    def activated_at(self) -> datetime | None:
        return self._state.activated_at

    # --------------------------------------------------
    # Backward-compatible API
    # --------------------------------------------------

    def is_active(self) -> bool:
        """
        Backward-compatible method for legacy callers.

        Returns:
            True when the kill switch is active.
        """
        return self.active

    # --------------------------------------------------
    # Activation
    # --------------------------------------------------

    def activate(
        self,
        reason: str = DEFAULT_REASON,
    ) -> None:

        if not isinstance(
            reason,
            str,
        ):
            raise TypeError(
                "Reason must be a string."
            )

        normalized_reason = reason.strip()

        if not normalized_reason:
            raise ValueError(
                "Reason cannot be empty."
            )

        self._state = KillSwitchState(
            active=True,
            reason=normalized_reason,
            activated_at=datetime.now(UTC),
        )

    # --------------------------------------------------
    # Deactivation
    # --------------------------------------------------

    def deactivate(self) -> None:
        self._state = KillSwitchState()