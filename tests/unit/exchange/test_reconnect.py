from __future__ import annotations

import asyncio
from typing import Awaitable, Callable

from src.exchange.reconnect import ReconnectManager


class ExchangeWebSocket:
    """
    Generic WebSocket controller.

    This class is exchange-independent and will later
    be extended by Binance, Bybit, OKX, etc.
    """

    def __init__(
        self,
        reconnect: ReconnectManager | None = None,
    ) -> None:

        self._connected = False

        self._reconnect = reconnect or ReconnectManager()

    # -----------------------------------------------------

    @property
    def connected(self) -> bool:

        return self._connected

    # -----------------------------------------------------

    async def connect(self) -> bool:

        self._connected = True

        return True

    # -----------------------------------------------------

    async def disconnect(self) -> None:

        self._connected = False

    # -----------------------------------------------------

    async def reconnect(self) -> bool:

        return await self._reconnect.run(
            self.connect,
        )

    # -----------------------------------------------------

    async def listen(
        self,
        handler: Callable[[dict], Awaitable[None]],
    ) -> None:

        if not self._connected:

            raise RuntimeError(
                "WebSocket is not connected."
            )

        await handler({})