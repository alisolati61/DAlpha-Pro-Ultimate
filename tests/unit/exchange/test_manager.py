"""Behavioral tests for the exchange registry and shutdown lifecycle."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from src.exchange.base import BaseExchange
from src.exchange.manager import ExchangeManager


def run(coroutine: Any) -> Any:
    return asyncio.run(coroutine)


class FakeExchange(BaseExchange):
    def __init__(
        self,
        *,
        disconnect_error: Exception | None = None,
    ) -> None:
        self.connect_calls = 0
        self.disconnect_calls = 0
        self.disconnect_error = disconnect_error

    async def connect(self) -> None:
        self.connect_calls += 1

    async def disconnect(self) -> None:
        self.disconnect_calls += 1

        if self.disconnect_error is not None:
            raise self.disconnect_error

    async def health_check(self) -> bool:
        return True

    async def fetch_ticker(self, symbol: str) -> dict[str, str]:
        return {"symbol": symbol}

    async def fetch_balance(self) -> dict[str, Any]:
        return {}

    async def fetch_positions(self) -> list[Any]:
        return []

    async def fetch_orderbook(self, symbol: str) -> dict[str, str]:
        return {"symbol": symbol}

    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 500,
    ) -> list[Any]:
        return [symbol, timeframe, limit]

    async def create_order(
        self,
        *args: Any,
        **kwargs: Any,
    ) -> dict[str, Any]:
        return {"args": args, "kwargs": kwargs}

    async def cancel_order(self, order_id: str) -> dict[str, str]:
        return {"id": order_id}

    async def fetch_order(
        self,
        order_id: str,
        symbol: str | None = None,
    ) -> dict[str, str | None]:
        return {"id": order_id, "symbol": symbol}


class BlockingExchange(FakeExchange):
    def __init__(self) -> None:
        super().__init__()
        self.disconnect_started = asyncio.Event()
        self.allow_disconnect = asyncio.Event()

    async def disconnect(self) -> None:
        self.disconnect_calls += 1
        self.disconnect_started.set()
        await self.allow_disconnect.wait()


def test_register_get_and_exists_use_one_normalized_name() -> None:
    manager = ExchangeManager()
    exchange = FakeExchange()

    manager.register("  BiNaNcE  ", exchange)

    assert manager.get("binance") is exchange
    assert manager.get(" BINANCE ") is exchange
    assert manager.exists("Binance") is True
    assert " BINANCE " in manager
    assert "   " not in manager
    assert 123 not in manager
    assert manager.names() == ["binance"]
    assert manager.list() == ["binance"]
    assert len(manager) == 1


@pytest.mark.parametrize("name", ["", "   ", "\t\n"])
def test_empty_exchange_name_is_rejected(name: str) -> None:
    manager = ExchangeManager()

    with pytest.raises(
        ValueError,
        match="Exchange name cannot be empty",
    ):
        manager.register(name, FakeExchange())


@pytest.mark.parametrize("name", [None, 123, object()])
def test_non_string_exchange_name_is_rejected(name: object) -> None:
    manager = ExchangeManager()

    with pytest.raises(
        TypeError,
        match="Exchange name must be a string",
    ):
        manager.register(name, FakeExchange())  # type: ignore[arg-type]


def test_non_exchange_instance_is_rejected() -> None:
    manager = ExchangeManager()

    with pytest.raises(
        TypeError,
        match="BaseExchange contract",
    ):
        manager.register("binance", object())  # type: ignore[arg-type]


def test_duplicate_normalized_name_does_not_replace_existing_adapter() -> None:
    manager = ExchangeManager()
    original = FakeExchange()

    manager.register("binance", original)

    with pytest.raises(
        ValueError,
        match="already registered: binance",
    ):
        manager.register(" BINANCE ", FakeExchange())

    assert manager.get("binance") is original
    assert len(manager) == 1


def test_missing_exchange_has_descriptive_error() -> None:
    manager = ExchangeManager()

    with pytest.raises(
        KeyError,
        match="Exchange is not registered: bybit",
    ):
        manager.get(" BYBIT ")


def test_remove_returns_adapter_without_disconnecting_it() -> None:
    manager = ExchangeManager()
    exchange = FakeExchange()
    manager.register("binance", exchange)

    removed = manager.remove(" BINANCE ")

    assert removed is exchange
    assert exchange.disconnect_calls == 0
    assert manager.exists("binance") is False
    assert len(manager) == 0


def test_remove_missing_exchange_has_descriptive_error() -> None:
    manager = ExchangeManager()

    with pytest.raises(
        KeyError,
        match="Exchange is not registered: binance",
    ):
        manager.remove("binance")


def test_shutdown_disconnects_every_exchange_and_is_idempotent() -> None:
    manager = ExchangeManager()
    binance = FakeExchange()
    bybit = FakeExchange()
    manager.register("binance", binance)
    manager.register("bybit", bybit)

    async def scenario() -> None:
        await manager.shutdown()
        await manager.shutdown()

    run(scenario())

    assert binance.disconnect_calls == 1
    assert bybit.disconnect_calls == 1
    assert manager.names() == []


def test_shutdown_isolates_failures_and_keeps_them_retriable() -> None:
    manager = ExchangeManager()
    close_error = RuntimeError("close failed")
    broken = FakeExchange(disconnect_error=close_error)
    healthy = FakeExchange()
    manager.register("broken", broken)
    manager.register("healthy", healthy)

    async def scenario() -> None:
        with pytest.raises(ExceptionGroup) as captured:
            await manager.shutdown()

        assert len(captured.value.exceptions) == 1
        failure = captured.value.exceptions[0]
        assert "broken" in str(failure)
        assert "close failed" in str(failure)
        assert failure.__cause__ is close_error

        assert manager.names() == ["broken"]
        assert manager.get("broken") is broken

        broken.disconnect_error = None
        await manager.shutdown()

    run(scenario())

    assert broken.disconnect_calls == 2
    assert healthy.disconnect_calls == 1
    assert manager.names() == []


def test_registry_mutation_is_rejected_during_shutdown() -> None:
    manager = ExchangeManager()
    blocking = BlockingExchange()
    manager.register("blocking", blocking)

    async def scenario() -> None:
        shutdown_task = asyncio.create_task(manager.shutdown())
        await blocking.disconnect_started.wait()

        with pytest.raises(
            RuntimeError,
            match="shutdown is in progress",
        ):
            manager.register("late", FakeExchange())

        with pytest.raises(
            RuntimeError,
            match="shutdown is in progress",
        ):
            manager.remove("blocking")

        blocking.allow_disconnect.set()
        await shutdown_task

    run(scenario())

    assert manager.names() == []


def test_cancelled_shutdown_keeps_adapter_registered_for_retry() -> None:
    manager = ExchangeManager()
    blocking = BlockingExchange()
    manager.register("blocking", blocking)

    async def scenario() -> None:
        shutdown_task = asyncio.create_task(manager.shutdown())
        await blocking.disconnect_started.wait()
        shutdown_task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await shutdown_task

        assert manager.get("blocking") is blocking

        blocking.allow_disconnect.set()
        await manager.shutdown()

    run(scenario())

    assert blocking.disconnect_calls == 2
    assert manager.names() == []


def test_async_context_manager_shuts_down_registered_exchanges() -> None:
    exchange = FakeExchange()

    async def scenario() -> ExchangeManager:
        async with ExchangeManager() as manager:
            manager.register("binance", exchange)
            return manager

    manager = run(scenario())

    assert exchange.disconnect_calls == 1
    assert manager.names() == []


def test_async_context_manager_does_not_suppress_body_errors() -> None:
    exchange = FakeExchange()

    async def scenario() -> None:
        async with ExchangeManager() as manager:
            manager.register("binance", exchange)
            raise LookupError("body failed")

    with pytest.raises(LookupError, match="body failed"):
        run(scenario())

    assert exchange.disconnect_calls == 1