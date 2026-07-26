"""Tests for the stable asynchronous exchange contract."""

from __future__ import annotations

import asyncio
import inspect
from typing import Any

import pytest

from src.exchange.base import BaseExchange


EXPECTED_METHODS = (
    "cancel_order",
    "connect",
    "create_order",
    "disconnect",
    "fetch_balance",
    "fetch_ohlcv",
    "fetch_order",
    "fetch_orderbook",
    "fetch_positions",
    "fetch_ticker",
    "health_check",
)


class CompleteExchange(BaseExchange):
    def __init__(self) -> None:
        self.events: list[str] = []

    async def connect(self) -> None:
        self.events.append("connect")

    async def disconnect(self) -> None:
        self.events.append("disconnect")

    async def health_check(self) -> bool:
        return True

    async def fetch_ticker(
        self,
        symbol: str,
    ) -> dict[str, str]:
        return {"symbol": symbol}

    async def fetch_balance(self) -> dict[str, float]:
        return {"USDT": 100.0}

    async def fetch_positions(self) -> list[object]:
        return []

    async def fetch_orderbook(
        self,
        symbol: str,
    ) -> dict[str, object]:
        return {
            "symbol": symbol,
            "bids": [],
            "asks": [],
        }

    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 500,
    ) -> list[object]:
        return [
            symbol,
            timeframe,
            limit,
        ]

    async def create_order(
        self,
        *args: Any,
        **kwargs: Any,
    ) -> dict[str, object]:
        return {
            "args": args,
            "kwargs": kwargs,
        }

    async def cancel_order(
        self,
        order_id: str,
    ) -> dict[str, str]:
        return {"order_id": order_id}

    async def fetch_order(
        self,
        order_id: str,
        symbol: str | None = None,
    ) -> dict[str, str | None]:
        return {
            "order_id": order_id,
            "symbol": symbol,
        }


def run(coroutine: Any) -> Any:
    return asyncio.run(coroutine)


def test_cannot_instantiate() -> None:
    with pytest.raises(TypeError):
        BaseExchange()


def test_incomplete_subclass_cannot_instantiate() -> None:
    class IncompleteExchange(BaseExchange):
        async def connect(self) -> None:
            return None

    with pytest.raises(TypeError):
        IncompleteExchange()


def test_complete_subclass_can_be_instantiated() -> None:
    exchange = CompleteExchange()

    assert isinstance(exchange, BaseExchange)


def test_required_methods_are_exact_and_deterministic() -> None:
    assert BaseExchange.required_methods() == EXPECTED_METHODS
    assert len(EXPECTED_METHODS) == len(
        set(EXPECTED_METHODS)
    )


def test_every_required_method_is_abstract_coroutine() -> None:
    for method_name in EXPECTED_METHODS:
        method = getattr(
            BaseExchange,
            method_name,
        )

        assert inspect.iscoroutinefunction(method)
        assert getattr(
            method,
            "__isabstractmethod__",
            False,
        ) is True


def test_complete_implementation_has_no_abstract_methods() -> None:
    assert inspect.isabstract(
        CompleteExchange
    ) is False
    assert CompleteExchange.required_methods() == ()


def test_context_manager_connects_and_disconnects() -> None:
    exchange = CompleteExchange()

    async def scenario() -> None:
        async with exchange as entered:
            assert entered is exchange
            assert exchange.events == [
                "connect"
            ]

        assert exchange.events == [
            "connect",
            "disconnect",
        ]

    run(scenario())


def test_context_manager_does_not_suppress_exception() -> None:
    exchange = CompleteExchange()

    async def scenario() -> None:
        with pytest.raises(
            RuntimeError,
            match="boom",
        ):
            async with exchange:
                raise RuntimeError("boom")

    run(scenario())

    assert exchange.events == [
        "connect",
        "disconnect",
    ]


def test_connect_failure_does_not_call_disconnect() -> None:
    class FailingConnectExchange(
        CompleteExchange
    ):
        async def connect(self) -> None:
            self.events.append(
                "connect"
            )
            raise RuntimeError(
                "connect failed"
            )

    exchange = FailingConnectExchange()

    async def scenario() -> None:
        with pytest.raises(
            RuntimeError,
            match="connect failed",
        ):
            async with exchange:
                pass

    run(scenario())

    assert exchange.events == [
        "connect"
    ]


def test_disconnect_failure_propagates() -> None:
    class FailingDisconnectExchange(
        CompleteExchange
    ):
        async def disconnect(self) -> None:
            self.events.append(
                "disconnect"
            )
            raise RuntimeError(
                "disconnect failed"
            )

    exchange = FailingDisconnectExchange()

    async def scenario() -> None:
        with pytest.raises(
            RuntimeError,
            match="disconnect failed",
        ):
            async with exchange:
                pass

    run(scenario())

    assert exchange.events == [
        "connect",
        "disconnect",
    ]


def test_complete_exchange_methods_preserve_contract() -> None:
    exchange = CompleteExchange()

    async def scenario() -> None:
        assert (
            await exchange.health_check()
        ) is True
        assert await exchange.fetch_ticker(
            "BTC/USDT"
        ) == {
            "symbol": "BTC/USDT"
        }
        assert await exchange.fetch_balance() == {
            "USDT": 100.0
        }
        assert await exchange.fetch_positions() == []
        assert await exchange.fetch_orderbook(
            "BTC/USDT"
        ) == {
            "symbol": "BTC/USDT",
            "bids": [],
            "asks": [],
        }
        assert await exchange.fetch_ohlcv(
            "BTC/USDT",
            "1h",
        ) == [
            "BTC/USDT",
            "1h",
            500,
        ]
        assert await exchange.create_order(
            "BTC/USDT",
            side="buy",
        ) == {
            "args": (
                "BTC/USDT",
            ),
            "kwargs": {
                "side": "buy",
            },
        }
        assert await exchange.cancel_order(
            "order-1"
        ) == {
            "order_id": "order-1"
        }
        assert await exchange.fetch_order(
            "order-1",
            "BTC/USDT",
        ) == {
            "order_id": "order-1",
            "symbol": "BTC/USDT",
        }

    run(scenario())


def test_public_export_is_exact() -> None:
    import src.exchange.base as module

    assert module.__all__ == (
        "BaseExchange",
    )