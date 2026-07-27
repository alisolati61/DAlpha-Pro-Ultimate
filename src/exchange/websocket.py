"""Exchange-independent asynchronous WebSocket lifecycle manager."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from enum import Enum
from types import TracebackType
from typing import Any, Self, TypeAlias

from src.exchange.exceptions import ExchangeError, WebSocketError
from src.exchange.reconnect import ReconnectManager

Message: TypeAlias = dict[str, Any]
ConnectCallback: TypeAlias = Callable[[], Awaitable[object]]
DisconnectCallback: TypeAlias = Callable[[], Awaitable[None]]
ReceiveCallback: TypeAlias = Callable[
    [],
    Awaitable[Mapping[str, Any] | None],
]
MessageHandler: TypeAlias = Callable[[Message], Awaitable[None]]

_STOP = object()


class WebSocketState(str, Enum):
    """Lifecycle states exposed by :class:`WebSocketManager`."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTING = "disconnecting"


class WebSocketManager:
    """Coordinate a WebSocket transport without exchange-specific logic.

    Transport callbacks are optional. Without a receive callback, messages can
    be injected through :meth:`publish`, which is useful for adapters that own
    their network reader and for deterministic tests.
    """

    def __init__(
        self,
        reconnect: ReconnectManager | None = None,
        *,
        connect_callback: ConnectCallback | None = None,
        disconnect_callback: DisconnectCallback | None = None,
        receive_callback: ReceiveCallback | None = None,
        exchange: str = "unknown",
    ) -> None:
        self._connect_callback = self._validate_optional_callback(
            connect_callback,
            field_name="connect_callback",
        )
        self._disconnect_callback = self._validate_optional_callback(
            disconnect_callback,
            field_name="disconnect_callback",
        )
        self._receive_callback = self._validate_optional_callback(
            receive_callback,
            field_name="receive_callback",
        )

        if reconnect is not None and not isinstance(
            reconnect,
            ReconnectManager,
        ):
            raise TypeError(
                "reconnect must be a ReconnectManager or None."
            )

        if not isinstance(exchange, str):
            raise TypeError("exchange must be a string.")

        normalized_exchange = exchange.strip().casefold()

        if not normalized_exchange:
            raise ValueError("exchange cannot be empty.")

        self._exchange = normalized_exchange
        self._reconnect = reconnect or ReconnectManager()

        self._state = WebSocketState.DISCONNECTED
        self._lifecycle_lock = asyncio.Lock()
        self._listen_lock = asyncio.Lock()
        self._queue: asyncio.Queue[object] | None = None

    @property
    def state(self) -> WebSocketState:
        """Return the current lifecycle state."""

        return self._state

    @property
    def connected(self) -> bool:
        """Return whether the transport is connected."""

        return self._state is WebSocketState.CONNECTED

    @property
    def exchange(self) -> str:
        """Return the normalized exchange identifier."""

        return self._exchange

    async def connect(self) -> bool:
        """Open the transport once and initialize a fresh message queue."""

        async with self._lifecycle_lock:
            if self.connected:
                return True

            self._state = WebSocketState.CONNECTING

            try:
                result: object = True

                if self._connect_callback is not None:
                    result = await self._connect_callback()
            except asyncio.CancelledError:
                self._state = WebSocketState.DISCONNECTED
                raise
            except ExchangeError:
                self._state = WebSocketState.DISCONNECTED
                raise
            except Exception as exc:
                self._state = WebSocketState.DISCONNECTED
                raise WebSocketError(
                    message="WebSocket connection failed.",
                    exchange=self._exchange,
                    operation="connect",
                ) from exc

            if result is False:
                self._state = WebSocketState.DISCONNECTED
                return False

            self._queue = asyncio.Queue()
            self._state = WebSocketState.CONNECTED
            return True

    async def disconnect(self) -> None:
        """Close the transport once and unblock internal queue listeners."""

        async with self._lifecycle_lock:
            if self._state is WebSocketState.DISCONNECTED:
                return

            self._state = WebSocketState.DISCONNECTING
            queue = self._queue

            try:
                if self._disconnect_callback is not None:
                    await self._disconnect_callback()
            except asyncio.CancelledError:
                self._state = WebSocketState.DISCONNECTED
                self._signal_stop(queue)
                raise
            except ExchangeError:
                self._state = WebSocketState.DISCONNECTED
                self._signal_stop(queue)
                raise
            except Exception as exc:
                self._state = WebSocketState.DISCONNECTED
                self._signal_stop(queue)
                raise WebSocketError(
                    message="WebSocket disconnection failed.",
                    exchange=self._exchange,
                    operation="disconnect",
                ) from exc

            self._state = WebSocketState.DISCONNECTED
            self._signal_stop(queue)

    async def reconnect(self) -> bool:
        """Disconnect and reconnect using the configured retry policy."""

        if self._state is not WebSocketState.DISCONNECTED:
            await self.disconnect()

        connected = await self._reconnect.run(
            self.connect,
            retry_if=self._is_retryable,
        )

        if not connected:
            self._state = WebSocketState.DISCONNECTED

        return connected

    async def publish(self, message: Mapping[str, Any]) -> None:
        """Publish a transport-decoded message to the internal listener."""

        if not self.connected or self._queue is None:
            raise WebSocketError(
                message="WebSocket is not connected.",
                exchange=self._exchange,
                operation="publish",
            )

        normalized_message = self._normalize_message(message)
        await self._queue.put(normalized_message)

    async def listen(
        self,
        handler: MessageHandler,
        *,
        max_messages: int | None = None,
    ) -> None:
        """Receive and dispatch messages until closure or a message limit."""

        if not callable(handler):
            raise TypeError("handler must be callable.")

        normalized_limit = self._validate_message_limit(max_messages)

        if not self.connected:
            raise WebSocketError(
                message="WebSocket is not connected.",
                exchange=self._exchange,
                operation="listen",
            )

        async with self._listen_lock:
            handled = 0
            queue = self._queue

            while self.connected:
                message = await self._receive_next(queue)

                if message is None:
                    self._state = WebSocketState.DISCONNECTED
                    break

                await handler(message)
                handled += 1

                if (
                    normalized_limit is not None
                    and handled >= normalized_limit
                ):
                    break

    async def __aenter__(self) -> Self:
        connected = await self.connect()

        if not connected:
            raise WebSocketError(
                message="WebSocket connection was rejected.",
                exchange=self._exchange,
                operation="connect",
            )

        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        await self.disconnect()
        return False

    async def _receive_next(
        self,
        queue: asyncio.Queue[object] | None,
    ) -> Message | None:
        if self._receive_callback is None:
            if queue is None:
                raise WebSocketError(
                    message="WebSocket receive queue is unavailable.",
                    exchange=self._exchange,
                    operation="receive",
                )

            item = await queue.get()

            if item is _STOP:
                return None

            return self._normalize_message(item)

        try:
            message = await self._receive_callback()
        except asyncio.CancelledError:
            raise
        except ExchangeError:
            raise
        except Exception as exc:
            raise WebSocketError(
                message="WebSocket receive failed.",
                exchange=self._exchange,
                operation="receive",
            ) from exc

        if message is None:
            return None

        return self._normalize_message(message)

    @staticmethod
    def _signal_stop(
        queue: asyncio.Queue[object] | None,
    ) -> None:
        if queue is not None:
            queue.put_nowait(_STOP)

    @staticmethod
    def _normalize_message(
        message: object,
    ) -> Message:
        if not isinstance(message, Mapping):
            raise TypeError(
                "WebSocket message must be a mapping."
            )

        return dict(message)

    @staticmethod
    def _validate_message_limit(
        value: int | None,
    ) -> int | None:
        if value is None:
            return None

        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError(
                "max_messages must be an integer or None."
            )

        if value <= 0:
            raise ValueError(
                "max_messages must be greater than zero."
            )

        return value

    @staticmethod
    def _validate_optional_callback(
        callback: Callable[..., object] | None,
        *,
        field_name: str,
    ) -> Callable[..., object] | None:
        if callback is not None and not callable(callback):
            raise TypeError(
                f"{field_name} must be callable or None."
            )

        return callback

    @staticmethod
    def _is_retryable(error: Exception) -> bool:
        return bool(getattr(error, "retryable", True))


# Backward-compatible public name.
ExchangeWebSocket = WebSocketManager


__all__ = (
    "ConnectCallback",
    "DisconnectCallback",
    "ExchangeWebSocket",
    "Message",
    "MessageHandler",
    "ReceiveCallback",
    "WebSocketManager",
    "WebSocketState",
)