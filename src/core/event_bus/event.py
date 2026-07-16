from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import uuid4


@dataclass(slots=True)
class Event:
    """
    Base Event object for EventBus.
    """

    event_name: str = "Event"

    payload: dict = field(default_factory=dict)

    source: str = "system"

    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    event_id: str = field(default_factory=lambda: str(uuid4()))

    def __repr__(self) -> str:
        return (
            f"Event("
            f"id={self.event_id}, "
            f"name={self.event_name}, "
            f"source={self.source})"
        )