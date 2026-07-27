"""Behavioral tests for the generic WebSocket lifecycle manager."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from typing import Any

import pytest

from src.exchange.exceptions import (
    AuthenticationError,
    WebSocketError,
)
from src.exchange.reconnect import ReconnectManager
from src.exchange.websocket import (
    ExchangeWebSocket,
    WebSocketManager,
    WebSocketState,
)


def run(coroutine: Any) -> Any:
    return asyncio.run(coroutine)


class FakeSleeper:
    def __init__(self) -> None:
        self.delays: list[float] = []

    async def __call__(self, delay: float) -> None:
        self.delays.append(delay)
        await asyncio.sleep(0)


def test_backward_compatible_alias_is_preserved() -> None:
    assert ExchangeWebSocket is WebSocketManager


def test_default_transport_connects_and_disconnects_idempotently() -> None:
    manager = WebSocketManager(exchange="  BiNgX  ")

    async def scenario() -> None:
        assert manager.state is WebSocketState.DISCONNECTED
        assert await manager.connect() is True
        assert await manager.connect() is True
        assert manager.connected is True
        assert manager.exchange == "bingx"

        await manager.disconnect()
        await manager.disconnect()

    run(scenario())

    assert manager.connected is False
    assert manager.state is WebSocketState.DISCONNECTED


def test_transport_callbacks_are_called_once_per_lifecycle() -> None:
    connect_calls = 0
    disconnect_calls = 0

    async def connect() -> None:
        nonlocal connect_calls
        connect_calls += 1

    async def disconnect() -> None:
        nonlocal disconnect_calls
        disconnect_calls += 1

    manager = WebSocketManager(
        connect_callback=connect,
        disconnect_callback=disconnect,
    )

    async def scenario() -> None:
        await manager.connect()
        await manager.connect()
        await manager.disconnect()
        await manager.disconnect()

    run(scenario())

    assert connect_calls == 1
    assert disconnect_calls == 1


def test_explicit_false_connection_result_is_rejected() -> None:
    async def connect() -> bool:
        return False

    manager = WebSocketManager(connect_callback=connect)

    assert run(manager.connect()) is False
    assert manager.state is WebSocketState.DISCONNECTED


def test_connect_failure_is_wrapped_without_leaking_details() -> None:
    async def connect() -> None:
        raise RuntimeError("secret transport detail")

    manager = WebSocketManager(
        connect_callback=connect,
        exchange="bingx",
    )

    with pytest.raises(WebSocketError) as captured:
        run(manager.connect())

    error = captured.value
    assert error.exchange == "bingx"
    assert error.operation == "connect"
    assert error.retryable is True
    assert "secret transport detail" not in str(error)
    assert isinstance(error.__cause__, RuntimeError)
    assert manager.state is WebSocketState.DISCONNECTED


def test_existing_exchange_error_is_preserved() -> None:
    failure = AuthenticationError(
        "credentials rejected",
        exchange="bingx",
    )

    async def connect() -> None:
        raise failure

    manager = WebSocketManager(connect_callback=connect)

    with pytest.raises(AuthenticationError) as captured:
        run(manager.connect())

    assert captured.value is failure


def test_disconnect_failure_resets_state_and_is_wrapped() -> None:
    async def disconnect() -> None:
        raise RuntimeError("socket close failed")

    manager = WebSocketManager(
        disconnect_callback=disconnect,
        exchange="bingx",
    )

    async def scenario() -> None:
        await manager.connect()

        with pytest.raises(WebSocketError) as captured:
            await manager.disconnect()

        assert captured.value.operation == "disconnect"

    run(scenario())

    assert manager.state is WebSocketState.DISCONNECTED


def test_internal_queue_publish_and_listen_preserve_message_order() -> None:
    manager = WebSocketManager()
    received: list[dict[str, Any]] = []

    async def handler(message: dict[str, Any]) -> None:
        received.append(message)

    async def scenario() -> None:
        await manager.connect()
        await manager.publish({"sequence": 1})
        await manager.publish({"sequence": 2})
        await manager.listen(handler, max_messages=2)

    run(scenario())

    assert received == [
        {"sequence": 1},
        {"sequence": 2},
    ]
    assert manager.connected is True


def test_published_message_is_copied() -> None:
    manager = WebSocketManager()
    source = {"price": 100}
    received: list[dict[str, Any]] = []

    async def handler(message: dict[str, Any]) -> None:
        received.append(message)

    async def scenario() -> None:
        await manager.connect()
        await manager.publish(source)
        source["price"] = 200
        await manager.listen(handler, max_messages=1)

    run(scenario())

    assert received == [{"price": 100}]


def test_disconnect_unblocks_internal_listener() -> None:
    manager = WebSocketManager()
    received: list[dict[str, Any]] = []

    async def handler(message: dict[str, Any]) -> None:
        received.append(message)

    async def scenario() -> None:
        await manager.connect()
        listener = asyncio.create_task(manager.listen(handler))
        await asyncio.sleep(0)

        await manager.disconnect()
        await listener

    run(scenario())

    assert received == []
    assert manager.connected is False


def test_external_receiver_dispatches_until_remote_close() -> None:
    messages: Iterator[dict[str, int] | None] = iter(
        [
            {"sequence": 1},
            {"sequence": 2},
            None,
        ]
    )
    received: list[dict[str, Any]] = []

    async def receive() -> dict[str, int] | None:
        return next(messages)

    async def handler(message: dict[str, Any]) -> None:
        received.append(message)

    manager = WebSocketManager(receive_callback=receive)

    async def scenario() -> None:
        await manager.connect()
        await manager.listen(handler)

    run(scenario())

    assert received == [
        {"sequence": 1},
        {"sequence": 2},
    ]
    assert manager.state is WebSocketState.DISCONNECTED


def test_receive_failure_is_wrapped() -> None:
    async def receive() -> dict[str, Any]:
        raise OSError("low-level socket detail")

    async def handler(message: dict[str, Any]) -> None:
        return None

    manager = WebSocketManager(
        receive_callback=receive,
        exchange="bingx",
    )

    async def scenario() -> None:
        await manager.connect()

        with pytest.raises(WebSocketError) as captured:
            await manager.listen(handler)

        error = captured.value
        assert error.operation == "receive"
        assert error.exchange == "bingx"
        assert "low-level socket detail" not in str(error)
        assert isinstance(error.__cause__, OSError)

    run(scenario())


def test_handler_failure_is_not_hidden() -> None:
    manager = WebSocketManager()
    failure = LookupError("strategy handler failed")

    async def handler(message: dict[str, Any]) -> None:
        raise failure

    async def scenario() -> None:
        await manager.connect()
        await manager.publish({"event": "trade"})

        with pytest.raises(LookupError) as captured:
            await manager.listen(handler, max_messages=1)

        assert captured.value is failure

    run(scenario())


def test_reconnect_disconnects_then_retries() -> None:
    sleeper = FakeSleeper()
    reconnect = ReconnectManager(
        retries=3,
        delay=0.25,
        sleep=sleeper,
    )
    connect_results = iter([True, False, True])
    connect_calls = 0
    disconnect_calls = 0

    async def connect() -> bool:
        nonlocal connect_calls
        connect_calls += 1
        return next(connect_results)

    async def disconnect() -> None:
        nonlocal disconnect_calls
        disconnect_calls += 1

    manager = WebSocketManager(
        reconnect=reconnect,
        connect_callback=connect,
        disconnect_callback=disconnect,
    )

    async def scenario() -> None:
        assert await manager.connect() is True
        assert await manager.reconnect() is True

    run(scenario())

    assert connect_calls == 3
    assert disconnect_calls == 1
    assert sleeper.delays == [0.25]
    assert manager.connected is True


def test_reconnect_fails_fast_for_non_retryable_error() -> None:
    failure = AuthenticationError(
        "credentials rejected",
        exchange="bingx",
    )

    async def connect() -> None:
        raise failure

    manager = WebSocketManager(
        reconnect=ReconnectManager(
            retries=5,
            delay=0,
        ),
        connect_callback=connect,
    )

    with pytest.raises(AuthenticationError) as captured:
        run(manager.reconnect())

    assert captured.value is failure
    assert manager.state is WebSocketState.DISCONNECTED


def test_connect_cancellation_is_propagated_and_state_is_reset() -> None:
    async def connect() -> None:
        raise asyncio.CancelledError

    manager = WebSocketManager(connect_callback=connect)

    with pytest.raises(asyncio.CancelledError):
        run(manager.connect())

    assert manager.state is WebSocketState.DISCONNECTED


def test_async_context_manager_disconnects_and_preserves_body_error() -> None:
    disconnect_calls = 0

    async def disconnect() -> None:
        nonlocal disconnect_calls
        disconnect_calls += 1

    manager = WebSocketManager(
        disconnect_callback=disconnect,
    )

    async def scenario() -> None:
        async with manager:
            assert manager.connected is True
            raise LookupError("body failed")

    with pytest.raises(LookupError, match="body failed"):
        run(scenario())

    assert disconnect_calls == 1
    assert manager.connected is False


@pytest.mark.parametrize(
    "field_name",
    [
        "connect_callback",
        "disconnect_callback",
        "receive_callback",
    ],
)
def test_invalid_transport_callback_is_rejected(
    field_name: str,
) -> None:
    with pytest.raises(
        TypeError,
        match=f"{field_name} must be callable",
    ):
        WebSocketManager(
            **{field_name: object()}  # type: ignore[arg-type]
        )


def test_invalid_reconnect_manager_is_rejected() -> None:
    with pytest.raises(
        TypeError,
        match="reconnect must be a ReconnectManager",
    ):
        WebSocketManager(
            reconnect=object(),  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    ("exchange", "error_type"),
    [
        (123, TypeError),
        ("   ", ValueError),
    ],
)
def test_invalid_exchange_identifier_is_rejected(
    exchange: object,
    error_type: type[Exception],
) -> None:
    with pytest.raises(error_type):
        WebSocketManager(
            exchange=exchange,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    ("max_messages", "error_type"),
    [
        (True, TypeError),
        (1.5, TypeError),
        (0, ValueError),
        (-1, ValueError),
    ],
)
def test_invalid_message_limit_is_rejected(
    max_messages: object,
    error_type: type[Exception],
) -> None:
    manager = WebSocketManager()

    async def handler(message: dict[str, Any]) -> None:
        return None

    async def scenario() -> None:
        await manager.connect()

        with pytest.raises(error_type):
            await manager.listen(
                handler,
                max_messages=max_messages,  # type: ignore[arg-type]
            )

    run(scenario())


def test_listen_and_publish_require_connection() -> None:
    manager = WebSocketManager()

    async def handler(message: dict[str, Any]) -> None:
        return None

    async def scenario() -> None:
        with pytest.raises(WebSocketError) as listen_error:
            await manager.listen(handler)

        assert listen_error.value.operation == "listen"

        with pytest.raises(WebSocketError) as publish_error:
            await manager.publish({"event": "trade"})

        assert publish_error.value.operation == "publish"

    run(scenario())


def test_non_mapping_message_is_rejected() -> None:
    manager = WebSocketManager()

    async def scenario() -> None:
        await manager.connect()

        with pytest.raises(
            TypeError,
            match="message must be a mapping",
        ):
            await manager.publish(  # type: ignore[arg-type]
                ["not", "a", "mapping"]
            )

    run(scenario())