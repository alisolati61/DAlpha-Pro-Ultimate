from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Optional


@dataclass(slots=True)
class KillSwitchState:
    active: bool = False
    reason: str = ""
    activated_at: Optional[datetime] = None


class KillSwitch:
    """
    Emergency trading stop.

    When activated:
    - No new positions are allowed.
    - Existing positions should be closed by the execution engine.
    """

    def __init__(self) -> None:
        self._state = KillSwitchState()

    def activate(self, reason: str = "Manual activation") -> None:
        """
        Activate the kill switch.
        """
        self._state.active = True
        self._state.reason = reason
        self._state.activated_at = datetime.now(UTC)

    def deactivate(self) -> None:
        """
        Deactivate the kill switch.
        """
        self._state.active = False
        self._state.reason = ""
        self._state.activated_at = None

    @property
    def active(self) -> bool:
        return self._state.active

    @property
    def reason(self) -> str:
        return self._state.reason

    @property
    def activated_at(self) -> Optional[datetime]:
        return self._state.activated_at