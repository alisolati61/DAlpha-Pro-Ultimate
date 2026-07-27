"""Behavioral tests for the asynchronous exchange factory."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

import src.exchange.exchange_factory as factory_module
from src.exchange.base import BaseExchange
from src.exchange.exceptions import ExchangeError
from src.exchange.exchange_factory import (
    ExchangeFactory,
    ExchangeType,
)


class FakeExchange(BaseExchange):
    def __init__(self, **config: Any) -> None:
        self.config = dict(config)

    async def connect(self) -> None:
        return None

    async def disconnect(self) -> None:
        return None

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


@pytest.fixture(autouse=True)
def restore_factory_registry() -> Iterator[None]:
    with ExchangeFactory._registry_lock:
        snapshot = dict(ExchangeFactory._builders)

    try:
        yield
    finally:
        with ExchangeFactory._registry_lock:
            ExchangeFactory._builders = snapshot


def test_default_factory_creates_ccxt_adapter_without_connecting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, dict[str, Any]]] = []

    def fake_ccxt(
        exchange_name: str,
        **config: Any,
    ) -> FakeExchange:
        calls.append((exchange_name, dict(config)))
        return FakeExchange(**config)

    monkeypatch.setattr(
        factory_module,
        "CCXTExchange",
        fake_ccxt,
    )

    exchange = ExchangeFactory.create(
        "  BiNaNcE  ",
        apiKey="api-key",
        secret="api-secret",
        enableRateLimit=True,
    )

    assert isinstance(exchange, FakeExchange)
    assert calls == [
        (
            "binance",
            {
                "apiKey": "api-key",
                "secret": "api-secret",
                "enableRateLimit": True,
            },
        )
    ]


def test_factory_accepts_exchange_enum(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        factory_module,
        "CCXTExchange",
        lambda exchange_name, **config: FakeExchange(
            exchange_name=exchange_name,
            **config,
        ),
    )

    exchange = ExchangeFactory.create(ExchangeType.BINGX)

    assert exchange.config == {"exchange_name": "bingx"}


def test_default_registry_is_truthful_and_deterministic() -> None:
    assert ExchangeFactory.supported_exchanges() == [
        "binance",
        "bingx",
        "bybit",
        "kucoin",
        "okx",
    ]
    assert ExchangeFactory.is_registered(" BINGX ") is True
    assert ExchangeFactory.is_registered(ExchangeType.PAPER) is False


@pytest.mark.parametrize("exchange_type", ["", "   ", "\t\n"])
def test_empty_exchange_identifier_is_rejected(
    exchange_type: str,
) -> None:
    with pytest.raises(
        ValueError,
        match="Exchange type cannot be empty",
    ):
        ExchangeFactory.create(exchange_type)


@pytest.mark.parametrize(
    "exchange_type",
    [None, 123, object()],
)
def test_non_string_exchange_identifier_is_rejected(
    exchange_type: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="Exchange type must be",
    ):
        ExchangeFactory.create(  # type: ignore[arg-type]
            exchange_type
        )


def test_unregistered_exchange_has_clear_error() -> None:
    with pytest.raises(ExchangeError) as captured:
        ExchangeFactory.create("kraken")

    assert captured.value.exchange == "kraken"
    assert "Unsupported exchange: kraken" in str(captured.value)
    assert "binance" in str(captured.value)


def test_reserved_paper_exchange_is_not_silently_created() -> None:
    with pytest.raises(ExchangeError) as captured:
        ExchangeFactory.create(ExchangeType.PAPER)

    assert captured.value.exchange == "paper"
    assert "Unsupported exchange: paper" in str(captured.value)


def test_custom_builder_can_be_registered_and_created() -> None:
    ExchangeFactory.register("custom", FakeExchange)

    exchange = ExchangeFactory.create(
        " CUSTOM ",
        account="alpha",
    )

    assert isinstance(exchange, FakeExchange)
    assert exchange.config == {"account": "alpha"}
    assert ExchangeFactory.is_registered("custom") is True


def test_duplicate_builder_requires_explicit_replace() -> None:
    original_builder = lambda **config: FakeExchange(
        source="original",
        **config,
    )
    replacement_builder = lambda **config: FakeExchange(
        source="replacement",
        **config,
    )

    ExchangeFactory.register("custom", original_builder)

    with pytest.raises(
        ValueError,
        match="already registered: custom",
    ):
        ExchangeFactory.register(
            " CUSTOM ",
            replacement_builder,
        )

    assert ExchangeFactory.create("custom").config == {
        "source": "original"
    }

    ExchangeFactory.register(
        " CUSTOM ",
        replacement_builder,
        replace=True,
    )

    assert ExchangeFactory.create("custom").config == {
        "source": "replacement"
    }


def test_non_callable_builder_is_rejected() -> None:
    with pytest.raises(
        TypeError,
        match="builder must be callable",
    ):
        ExchangeFactory.register(
            "custom",
            object(),  # type: ignore[arg-type]
        )


def test_builder_must_return_base_exchange() -> None:
    ExchangeFactory.register(
        "broken",
        lambda **config: object(),  # type: ignore[arg-type]
    )

    with pytest.raises(
        TypeError,
        match="must return a BaseExchange",
    ):
        ExchangeFactory.create("broken")


def test_builder_failure_is_wrapped_without_leaking_config() -> None:
    def broken_builder(**config: Any) -> BaseExchange:
        raise RuntimeError("constructor failed")

    ExchangeFactory.register("broken", broken_builder)

    with pytest.raises(ExchangeError) as captured:
        ExchangeFactory.create(
            "broken",
            secret="super-secret",
        )

    assert captured.value.exchange == "broken"
    assert "Failed to create exchange adapter: broken" in str(
        captured.value
    )
    assert "super-secret" not in str(captured.value)
    assert isinstance(captured.value.__cause__, RuntimeError)


def test_exchange_error_from_builder_is_preserved() -> None:
    original = ExchangeError(
        message="credentials rejected",
        exchange="custom",
    )

    def broken_builder(**config: Any) -> BaseExchange:
        raise original

    ExchangeFactory.register("custom", broken_builder)

    with pytest.raises(ExchangeError) as captured:
        ExchangeFactory.create("custom")

    assert captured.value is original


def test_unregister_returns_builder_and_removes_exchange() -> None:
    ExchangeFactory.register("custom", FakeExchange)

    removed = ExchangeFactory.unregister(" CUSTOM ")

    assert removed is FakeExchange
    assert ExchangeFactory.is_registered("custom") is False

    with pytest.raises(ExchangeError) as captured:
        ExchangeFactory.unregister("custom")

    assert captured.value.exchange == "custom"
    assert "not registered: custom" in str(captured.value)