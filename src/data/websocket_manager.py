from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class WebSocketState:
    connected: bool = False
    endpoint: str = ""


class WebSocketManager:
    """
    Generic WebSocket manager.

    Future
    -------
    - Binance WebSocket
    - Bybit WebSocket
    - OKX WebSocket
    - Auto Reconnect
    - Heartbeat
    """

    def __init__(self) -> None:

        self._state = WebSocketState()

    # -------------------------------------

    def connect(
        self,
        endpoint: str,
    ) -> None:

        self._state.endpoint = endpoint

        self._state.connected = True

    # -------------------------------------

    def disconnect(self) -> None:

        self._state.connected = False

    # -------------------------------------

    @property
    def connected(self) -> bool:

        return self._state.connected

    # -------------------------------------

    @property
    def endpoint(self) -> str:

        return self._state.endpoint