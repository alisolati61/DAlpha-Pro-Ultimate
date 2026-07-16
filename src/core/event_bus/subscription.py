from __future__ import annotations

from collections import defaultdict

from .event import Event
from .exceptions import (
    DuplicateSubscriptionError,
    HandlerNotFoundError,
)
from .types import EventHandler, EventType


class SubscriptionManager:
    """
    Manages subscriptions for the Event Bus.

    Responsible for:

    - subscribe
    - unsubscribe
    - lookup handlers
    """

    def __init__(self) -> None:
        self._subscriptions: dict[
            EventType,
            list[EventHandler],
        ] = defaultdict(list)

    def subscribe(
        self,
        event_type: EventType,
        handler: EventHandler,
    ) -> None:

        handlers = self._subscriptions[event_type]

        if handler in handlers:
            raise DuplicateSubscriptionError(
                f"{handler} already subscribed."
            )

        handlers.append(handler)

    def unsubscribe(
        self,
        event_type: EventType,
        handler: EventHandler,
    ) -> None:

        handlers = self._subscriptions.get(event_type)

        if handlers is None or handler not in handlers:
            raise HandlerNotFoundError(
                f"{handler} not subscribed."
            )

        handlers.remove(handler)

    def handlers_for(
        self,
        event_type: EventType,
    ) -> list[EventHandler]:

        return list(
            self._subscriptions.get(event_type, [])
        )

    def clear(self) -> None:
        self._subscriptions.clear()

    def count(self) -> int:
        return sum(
            len(v)
            for v in self._subscriptions.values()
        )