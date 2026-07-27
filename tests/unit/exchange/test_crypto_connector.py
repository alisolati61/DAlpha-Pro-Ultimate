"""Behavioral tests for the high-level crypto connector."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from src.exchange.base import BaseExchange
from src.exchange.connectors.crypto_connector import CryptoConnector
from src.exchange.exchange_factory import ExchangeType


def run(coroutine: Any) -> Any:
    return asyncio.run(coroutine)


class FakeExchange(BaseExchange):
    def __init__(self, exchange_name: str = "fake") -> None:
        self.exchange_name = exchange_name
        self.calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []

    def _record(
        self,
        operation: str,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        self.calls.append((operation, args, kwargs))

    async def connect(self) -> None:
        self._record("connect")

    async def disconnect(self) -> None:
        self._record("disconnect")

    async def health_check(self) -> bool:
        self._record("health_check")
        return True

    async def fetch_balance(self) -> dict[str, float]:
        self._record("fetch_balance")
        return {"USDT": 100.0}

    async def fetch_positions(self) -> list[dict[str, str]]:
        self._record("fetch_positions")
        return [{"symbol": "BTC/USDT"}]

    async def fetch_ticker(self, symbol: str) -> dict[str, str]:
        self._record("fetch_ticker", symbol)
        return {"symbol": symbol}

    async def fetch_orderbook(self, symbol: str) -> dict[str, str]:
        self._record("fetch_orderbook", symbol)
        return {"symbol": symbol}

    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 500,
    ) -> list[Any]:
        self._record(
            "fetch_ohlcv",
            symbol,
            timeframe,
            limit=limit,
        )
        return [symbol, timeframe, limit]

    async def create_order(
        self,
        *args: Any,
        **kwargs: Any,
    ) -> dict[str, Any]:
        self._record("create_order", *args, **kwargs)
        return {"args": args, "kwargs": kwargs}

    async def cancel_order(self, order_id: str) -> dict[str, str]:
        self._record("cancel_order", order_id)
        return {"id": order_id}

    async def fetch_order(
        self,
        order_id: str,
        symbol: str | None = None,
    ) -> dict[str, str | None]:
        self._record("fetch_order", order_id, symbol)
        return {"id": order_id, "symbol": symbol}


def test_connector_implements_base_exchange_contract() -> None:
    connector = CryptoConnector(exchange=FakeExchange())

    assert isinstance(connector, BaseExchange)
    assert isinstance(connector.exchange, FakeExchange)


def test_factory_receives_exchange_name_and_configuration() -> None:
    calls: list[tuple[ExchangeType | str, dict[str, Any]]] = []
    exchange = FakeExchange(exchange_name="binance")

    def factory(
        exchange_name: ExchangeType | str,
        **config: Any,
    ) -> BaseExchange:
        calls.append((exchange_name, dict(config)))
        return exchange

    connector = CryptoConnector(
        "  BiNaNcE  ",
        factory=factory,
        apiKey="api-key",
        secret="api-secret",
    )

    assert connector.exchange is exchange
    assert connector.exchange_name == "binance"
    assert calls == [
        (
            "  BiNaNcE  ",
            {
                "apiKey": "api-key",
                "secret": "api-secret",
            },
        )
    ]


def test_exchange_enum_is_supported() -> None:
    exchange = FakeExchange(exchange_name="bingx")

    connector = CryptoConnector(
        ExchangeType.BINGX,
        factory=lambda exchange_name, **config: exchange,
    )

    assert connector.exchange_name == "bingx"


def test_injected_adapter_name_takes_precedence() -> None:
    connector = CryptoConnector(
        "ignored",
        exchange=FakeExchange(exchange_name="  ByBiT  "),
    )

    assert connector.exchange_name == "bybit"


def test_injected_exchange_rejects_ambiguous_inputs() -> None:
    exchange = FakeExchange()

    with pytest.raises(
        ValueError,
        match="config cannot be supplied",
    ):
        CryptoConnector(exchange=exchange, apiKey="not-used")

    with pytest.raises(
        ValueError,
        match="factory cannot be supplied",
    ):
        CryptoConnector(
            exchange=exchange,
            factory=lambda exchange_name, **config: exchange,
        )


def test_invalid_injected_exchange_is_rejected() -> None:
    with pytest.raises(
        TypeError,
        match="BaseExchange contract",
    ):
        CryptoConnector(
            exchange=object(),  # type: ignore[arg-type]
        )


def test_invalid_factory_is_rejected() -> None:
    with pytest.raises(
        TypeError,
        match="factory must be callable",
    ):
        CryptoConnector(
            factory=object(),  # type: ignore[arg-type]
        )


def test_invalid_factory_result_is_rejected() -> None:
    with pytest.raises(
        TypeError,
        match="factory must return a BaseExchange",
    ):
        CryptoConnector(
            factory=lambda exchange_name, **config: object(),  # type: ignore[return-value]
        )


@pytest.mark.parametrize(
    ("exchange_name", "error_type"),
    [
        ("   ", ValueError),
        (123, TypeError),
    ],
)
def test_invalid_exchange_name_is_rejected_before_factory_call(
    exchange_name: object,
    error_type: type[Exception],
) -> None:
    called = False

    def factory(
        name: ExchangeType | str,
        **config: Any,
    ) -> BaseExchange:
        nonlocal called
        called = True
        return FakeExchange()

    with pytest.raises(error_type):
        CryptoConnector(
            exchange_name,  # type: ignore[arg-type]
            factory=factory,
        )

    assert called is False


def test_canonical_operations_delegate_without_data_changes() -> None:
    exchange = FakeExchange()
    connector = CryptoConnector(exchange=exchange)

    async def scenario() -> None:
        await connector.connect()
        assert await connector.health_check() is True
        assert await connector.fetch_balance() == {"USDT": 100.0}
        assert await connector.fetch_positions() == [
            {"symbol": "BTC/USDT"}
        ]
        assert await connector.fetch_ticker("BTC/USDT") == {
            "symbol": "BTC/USDT"
        }
        assert await connector.fetch_orderbook("BTC/USDT") == {
            "symbol": "BTC/USDT"
        }
        assert await connector.fetch_ohlcv(
            "BTC/USDT",
            "1h",
            limit=25,
        ) == ["BTC/USDT", "1h", 25]
        assert await connector.cancel_order("order-1") == {
            "id": "order-1"
        }
        assert await connector.fetch_order(
            "order-1",
            "BTC/USDT",
        ) == {
            "id": "order-1",
            "symbol": "BTC/USDT",
        }
        await connector.disconnect()

    run(scenario())

    assert exchange.calls == [
        ("connect", (), {}),
        ("health_check", (), {}),
        ("fetch_balance", (), {}),
        ("fetch_positions", (), {}),
        ("fetch_ticker", ("BTC/USDT",), {}),
        ("fetch_orderbook", ("BTC/USDT",), {}),
        (
            "fetch_ohlcv",
            ("BTC/USDT", "1h"),
            {"limit": 25},
        ),
        ("cancel_order", ("order-1",), {}),
        ("fetch_order", ("order-1", "BTC/USDT"), {}),
        ("disconnect", (), {}),
    ]


def test_create_order_translates_facade_order_to_ccxt_order() -> None:
    exchange = FakeExchange()
    connector = CryptoConnector(exchange=exchange)

    result = run(
        connector.create_order(
            "BTC/USDT",
            "buy",
            "limit",
            0.5,
            50_000.0,
            reduceOnly=True,
        )
    )

    assert result == {
        "args": (
            "BTC/USDT",
            "limit",
            "buy",
            0.5,
            50_000.0,
        ),
        "kwargs": {"reduceOnly": True},
    }


def test_legacy_aliases_delegate_to_canonical_operations() -> None:
    exchange = FakeExchange()
    connector = CryptoConnector(exchange=exchange)

    async def scenario() -> None:
        assert await connector.health() is True
        assert await connector.get_balance() == {"USDT": 100.0}
        assert await connector.get_positions() == [
            {"symbol": "BTC/USDT"}
        ]
        assert await connector.get_ticker("BTC/USDT") == {
            "symbol": "BTC/USDT"
        }
        assert await connector.get_orderbook("BTC/USDT") == {
            "symbol": "BTC/USDT"
        }
        assert await connector.get_ohlcv(
            "BTC/USDT",
            "5m",
            limit=10,
        ) == ["BTC/USDT", "5m", 10]

    run(scenario())


def test_async_context_manager_uses_owned_exchange_lifecycle() -> None:
    exchange = FakeExchange()
    connector = CryptoConnector(exchange=exchange)

    async def scenario() -> None:
        async with connector as active:
            assert active is connector
            raise LookupError("body failed")

    with pytest.raises(LookupError, match="body failed"):
        run(scenario())

    assert exchange.calls == [
        ("connect", (), {}),
        ("disconnect", (), {}),
    ]