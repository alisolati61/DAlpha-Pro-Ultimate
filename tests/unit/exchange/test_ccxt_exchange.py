"""Behavioral tests for the asynchronous CCXT exchange adapter."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

pytest.importorskip("ccxt.async_support")

import src.exchange.ccxt_exchange as ccxt_module
from src.exchange.base import BaseExchange
from src.exchange.ccxt_exchange import CCXTExchange


def run(coroutine: Any) -> Any:
    return asyncio.run(coroutine)


class FakeCCXTClient:
    def __init__(self, config: dict[str, Any]) -> None:
        self.config = dict(config)

        self.load_markets_calls = 0
        self.close_calls = 0
        self.fetch_time_calls = 0

        self.fail_fetch_time = False

    async def load_markets(self) -> dict[str, Any]:
        self.load_markets_calls += 1
        return {"BTC/USDT": {}}

    async def close(self) -> None:
        self.close_calls += 1

    async def fetch_time(self) -> int:
        self.fetch_time_calls += 1

        if self.fail_fetch_time:
            raise RuntimeError("exchange unavailable")

        return 1_700_000_000_000

    async def fetch_balance(self) -> dict[str, Any]:
        return {
            "USDT": {
                "free": 100.0,
                "used": 20.0,
                "total": 120.0,
            }
        }

    async def fetch_positions(self) -> list[dict[str, Any]]:
        return [{"symbol": "BTC/USDT", "contracts": 1.0}]

    async def fetch_ticker(self, symbol: str) -> dict[str, Any]:
        return {
            "symbol": symbol,
            "last": 50_000.0,
        }

    async def fetch_order_book(self, symbol: str) -> dict[str, Any]:
        return {
            "symbol": symbol,
            "bids": [[49_999.0, 1.0]],
            "asks": [[50_001.0, 1.0]],
        }

    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        *,
        limit: int,
    ) -> list[Any]:
        return [symbol, timeframe, limit]

    async def create_order(
        self,
        *args: Any,
        **kwargs: Any,
    ) -> dict[str, Any]:
        return {
            "args": args,
            "kwargs": kwargs,
        }

    async def cancel_order(
        self,
        order_id: str,
    ) -> dict[str, str]:
        return {"id": order_id}

    async def fetch_order(
        self,
        order_id: str,
        symbol: str | None,
    ) -> dict[str, str | None]:
        return {
            "id": order_id,
            "symbol": symbol,
        }


@pytest.fixture
def exchange_pair(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[CCXTExchange, FakeCCXTClient]:
    created: dict[str, FakeCCXTClient] = {}

    def factory(config: dict[str, Any]) -> FakeCCXTClient:
        client = FakeCCXTClient(config)
        created["client"] = client
        return client

    monkeypatch.setattr(
        ccxt_module.ccxt,
        "binance",
        factory,
    )

    exchange = CCXTExchange(
        "binance",
        apiKey="api-key",
        secret="api-secret",
        enableRateLimit=True,
    )

    return exchange, created["client"]


def test_implements_base_exchange_contract(
    exchange_pair: tuple[CCXTExchange, FakeCCXTClient],
) -> None:
    exchange, client = exchange_pair

    assert isinstance(exchange, BaseExchange)
    assert exchange.exchange is client


def test_passes_configuration_to_ccxt(
    exchange_pair: tuple[CCXTExchange, FakeCCXTClient],
) -> None:
    _, client = exchange_pair

    assert client.config == {
        "apiKey": "api-key",
        "secret": "api-secret",
        "enableRateLimit": True,
    }


def test_invalid_exchange_name_has_clear_error() -> None:
    with pytest.raises(
        ValueError,
        match="Unsupported CCXT exchange",
    ):
        CCXTExchange("exchange-that-does-not-exist")


def test_connection_lifecycle_is_idempotent(
    exchange_pair: tuple[CCXTExchange, FakeCCXTClient],
) -> None:
    exchange, client = exchange_pair

    async def scenario() -> None:
        assert await exchange.health_check() is False

        await exchange.connect()
        await exchange.connect()

        assert await exchange.health_check() is True

        await exchange.disconnect()
        await exchange.disconnect()

        assert await exchange.health_check() is False

    run(scenario())

    assert client.load_markets_calls == 1
    assert client.close_calls == 1
    assert client.fetch_time_calls == 1


def test_health_check_handles_exchange_failure(
    exchange_pair: tuple[CCXTExchange, FakeCCXTClient],
) -> None:
    exchange, client = exchange_pair
    client.fail_fetch_time = True

    async def scenario() -> None:
        await exchange.connect()

        assert await exchange.health_check() is False

        await exchange.disconnect()

    run(scenario())


def test_exchange_operations_delegate_to_ccxt(
    exchange_pair: tuple[CCXTExchange, FakeCCXTClient],
) -> None:
    exchange, _ = exchange_pair

    async def scenario() -> None:
        assert await exchange.fetch_balance() == {
            "USDT": {
                "free": 100.0,
                "used": 20.0,
                "total": 120.0,
            }
        }

        assert await exchange.fetch_positions() == [
            {
                "symbol": "BTC/USDT",
                "contracts": 1.0,
            }
        ]

        assert await exchange.fetch_ticker(
            "BTC/USDT"
        ) == {
            "symbol": "BTC/USDT",
            "last": 50_000.0,
        }

        assert await exchange.fetch_orderbook(
            "BTC/USDT"
        ) == {
            "symbol": "BTC/USDT",
            "bids": [[49_999.0, 1.0]],
            "asks": [[50_001.0, 1.0]],
        }

        assert await exchange.fetch_ohlcv(
            "BTC/USDT",
            "1h",
            limit=25,
        ) == [
            "BTC/USDT",
            "1h",
            25,
        ]

        assert await exchange.create_order(
            "BTC/USDT",
            "limit",
            "buy",
            1.0,
            50_000.0,
        ) == {
            "args": (
                "BTC/USDT",
                "limit",
                "buy",
                1.0,
                50_000.0,
            ),
            "kwargs": {},
        }

        assert await exchange.cancel_order(
            "order-1"
        ) == {
            "id": "order-1"
        }

        assert await exchange.fetch_order(
            "order-1",
            "BTC/USDT",
        ) == {
            "id": "order-1",
            "symbol": "BTC/USDT",
        }

    run(scenario())


def test_missing_fetch_positions_capability_returns_empty_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class ClientWithoutPositions:
        pass

    monkeypatch.setattr(
        ccxt_module.ccxt,
        "kraken",
        lambda config: ClientWithoutPositions(),
    )

    exchange = CCXTExchange("kraken")

    assert run(exchange.fetch_positions()) == []
