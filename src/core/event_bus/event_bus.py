from __future__ import annotations

from collections import defaultdict
from typing import DefaultDict

from .event import Event
from .handler import EventHandler
from .types import Handler


class EventBus:
    """
    Central Event Bus.

    Responsible for:

    - subscribe
    - unsubscribe
    - publish

    This is the heart of DAlpha-Pro-Ultimate.
    """

    def __init__(self):

        self._subscriptions: DefaultDict[
            str,
            list[EventHandler],
        ] = defaultdict(list)

    def subscribe(
        self,
        event_name: str,
        callback: Handler,
    ) -> None:

        handler = EventHandler(callback)

        self._subscriptions[event_name].append(handler)

    def unsubscribe(
        self,
        event_name: str,
        callback: Handler,
    ) -> None:

        handlers = self._subscriptions.get(
            event_name,
            [],
        )

        self._subscriptions[event_name] = [
            handler
            for handler in handlers
            if handler.callback != callback
        ]

    def publish(
        self,
        event: Event,
    ) -> None:

        handlers = self._subscriptions.get(
            event.event_name,
            [],
        )

        for handler in handlers:

            handler.handle(event)

    def listener_count(
        self,
        event_name: str,
    ) -> int:

        return len(
            self._subscriptions.get(
                event_name,
                [],
            )
        )

    def clear(self) -> None:

        self._subscriptions.clear()