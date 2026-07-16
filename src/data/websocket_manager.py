from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable


class WebSocketManager:
    """
    Base websocket manager.

    Exchange adapters (Binance, Bybit, OKX...)
    will use this class.
    """

    def __init__(self):

        self._running = False

        self._callbacks: list[
            Callable[[dict], Awaitable[None]]
        ] = []

    def subscribe(

        self,

        callback: Callable[[dict], Awaitable[None]],

    ) -> None:

        self._callbacks.append(callback)

    async def publish(

        self,

        message: dict,

    ) -> None:

        for callback in self._callbacks:

            await callback(message)

    async def start(self):

        self._running = True

    async def stop(self):

        self._running = False

    @property
    def running(self):

        return self._running