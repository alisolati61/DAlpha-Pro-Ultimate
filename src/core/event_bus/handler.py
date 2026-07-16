from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .event import Event
from .types import Handler


@dataclass(slots=True)
class EventHandler:
    """
    Wraps a callback function.
    """

    callback: Handler

    def handle(self, event: Event) -> Any:
        return self.callback(event)