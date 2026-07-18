from __future__ import annotations

from collections import defaultdict
from typing import Callable


class DataRouter:
    """
    Event Router for Data Engine.

    Responsible for dispatching market events
    to subscribed modules.

    Future
    -------
    - Async dispatch
    - Priority routing
    - Event filtering
    """

    def __init__(self) -> None:

        self._handlers: dict[
            str,
            list[Callable],
        ] = defaultdict(list)

    # ---------------------------------------------

    def subscribe(
        self,
        event: str,
        callback: Callable,
    ) -> None:

        if callback not in self._handlers[event]:

            self._handlers[event].append(callback)

    # ---------------------------------------------

    def unsubscribe(
        self,
        event: str,
        callback: Callable,
    ) -> None:

        if callback in self._handlers[event]:

            self._handlers[event].remove(callback)

    # ---------------------------------------------

    def publish(
        self,
        event: str,
        payload,
    ) -> None:

        for callback in self._handlers[event]:

            callback(payload)

    # ---------------------------------------------

    def subscribers(
        self,
        event: str,
    ) -> int:

        return len(self._handlers[event])

    # ---------------------------------------------

    def clear(self) -> None:

        self._handlers.clear()