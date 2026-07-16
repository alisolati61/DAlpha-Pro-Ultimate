from __future__ import annotations

from typing import Callable, Protocol, TypeAlias

from .event import Event


class EventHandler(Protocol):
    """
    Protocol for every event handler.

    Any callable matching this signature can subscribe
    to the Event Bus.
    """

    def __call__(self, event: Event) -> None:
        ...


Handler: TypeAlias = Callable[[Event], None]
EventType: TypeAlias = type[Event]