from __future__ import annotations

from typing import Awaitable, Callable

from src.exchange.reconnect import ReconnectManager


class WebSocketManager:
    """
    Generic exchange-independent WebSocket manager.

    Provides:
    - connect
    - disconnect
    - reconnect
    - connection state tracking
    - message handler dispatch
    """

    def __init__(
        self,
        reconnect: ReconnectManager | None = None,
    ) -> None:

        self._connected = False

        self._reconnect = (
            reconnect
            if reconnect is not None
            else ReconnectManager()
        )

    @property
    def connected(
        self,
    ) -> bool:

        return self._connected

    async def connect(
        self,
    ) -> bool:

        self._connected = True

        return True

    async def disconnect(
        self,
    ) -> None:

        self._connected = False

    async def reconnect(
        self,
    ) -> bool:

        return await self._reconnect.run(
            self.connect,
        )

    async def listen(
        self,
        handler: Callable[
            [dict],
            Awaitable[None],
        ],
    ) -> None:

        if not self._connected:

            raise RuntimeError(
                "WebSocket is not connected."
            )

        await handler({})


# Backward-compatible alias.
ExchangeWebSocket = WebSocketManager