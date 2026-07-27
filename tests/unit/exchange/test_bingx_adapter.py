"""Behavioral tests for the asynchronous BingX adapter."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest

from src.exchange.base import BaseExchange
from src.exchange.bingx_adapter import BingXAdapter
from src.exchange.exceptions import ExchangeError, OrderError
from src.exchange.models import (
    BingXBalance,
    BingXFundingRate,
    BingXKline,
    BingXOrder,
    BingXOrderBook,
    BingXPosition,
    BingXTicker,
    BingXTrade,
)


def run(coroutine: Any) -> Any:
    return asyncio.run(coroutine)


def make_order(
    order_id: str = "order-1",
    symbol: str = "BTC-USDT",
    *,
    status: str = "NEW",
) -> BingXOrder:
    return BingXOrder(
        order_id=order_id,
        symbol=symbol,
        side="BUY",
        position_side="LONG",
        order_type="LIMIT",
        status=status,
        price="100",
        quantity="2",
        executed_qty="0.5",
        avg_price="100",
        created_at=1_700_000_000_000,
        updated_at=1_700_000_001_000,
    )


class FakeBingXClient:
    def __init__(
        self,
        *,
        demo_mode: bool = False,
        server_error: Exception | None = None,
    ) -> None:
        self.demo_mode = demo_mode
        self.server_error = server_error
        self.server_time_calls = 0
        self.close_calls = 0
        self.place_order_calls: list[dict[str, Any]] = []
        self.cancel_order_calls: list[tuple[str, str]] = []
        self.get_order_calls: list[tuple[str, str]] = []
        self.open_orders: list[BingXOrder] = []
        self.order = make_order()

    async def get_server_time(self) -> int:
        self.server_time_calls += 1

        if self.server_error is not None:
            raise self.server_error

        return 1_700_000_000_000

    async def close(self) -> None:
        self.close_calls += 1

    async def get_balance(self) -> list[BingXBalance]:
        return [
            BingXBalance(
                asset="USDT",
                wallet_balance="100",
                unrealized_pnl="5",
                margin_balance="105",
                available_balance="80",
                max_withdraw_amount="75",
            )
        ]

    async def get_positions(self) -> list[BingXPosition]:
        return [
            BingXPosition(
                symbol="BTC-USDT",
                position_side="SHORT",
                position_amount="2",
                entry_price="100",
                mark_price="90",
                unrealized_pnl="20",
                liquidation_price="150",
                leverage=10,
                margin_type="ISOLATED",
                isolated_margin="20",
            )
        ]

    async def get_ticker(self, symbol: str) -> BingXTicker:
        return BingXTicker(
            symbol=symbol,
            last_price="101",
            price_change="1",
            price_change_percent="1",
            high_price="110",
            low_price="90",
            volume="20",
            quote_volume="2000",
            bid_price="100",
            ask_price="102",
            close_time=1_700_000_000_000,
        )

    async def get_orderbook(
        self,
        symbol: str,
    ) -> BingXOrderBook:
        return BingXOrderBook(
            symbol=symbol,
            last_update_id=42,
            bids=[("100", "2")],
            asks=[("101", "3")],
        )

    async def get_klines(
        self,
        symbol: str,
        interval: str,
        limit: int,
    ) -> list[BingXKline]:
        return [
            BingXKline(
                open_time=1_700_000_000_000,
                open="100",
                high="110",
                low="90",
                close="105",
                volume="10",
                close_time=1_700_000_059_999,
                quote_volume="1000",
                trades_count=20,
                taker_buy_volume="6",
                taker_buy_quote_volume="600",
            )
        ]

    async def place_order(self, **kwargs: Any) -> BingXOrder:
        self.place_order_calls.append(dict(kwargs))
        return self.order

    async def cancel_order(
        self,
        symbol: str,
        order_id: str,
    ) -> dict[str, Any]:
        self.cancel_order_calls.append((symbol, order_id))
        return {"code": 0}

    async def get_order(
        self,
        symbol: str,
        order_id: str,
    ) -> BingXOrder:
        self.get_order_calls.append((symbol, order_id))
        return self.order

    async def get_open_orders(
        self,
        symbol: str | None = None,
    ) -> list[BingXOrder]:
        if symbol is None:
            return list(self.open_orders)

        return [
            order
            for order in self.open_orders
            if order.symbol == symbol
        ]

    async def get_funding_rate(
        self,
        symbol: str,
    ) -> BingXFundingRate:
        return BingXFundingRate(
            symbol=symbol,
            funding_rate="-0.0001",
            funding_time=1_700_000_000_000,
            mark_price="101",
        )

    async def get_recent_trades(
        self,
        symbol: str,
        limit: int,
    ) -> list[BingXTrade]:
        return [
            BingXTrade(
                trade_id=7,
                price="100.5",
                quantity="0.25",
                side="SELL",
                timestamp=1_700_000_000_000,
            )
        ]

    async def set_leverage(
        self,
        symbol: str,
        leverage: int,
        position_side: str,
    ) -> dict[str, Any]:
        return {
            "symbol": symbol,
            "leverage": leverage,
            "position_side": position_side,
        }

    async def set_margin_type(
        self,
        symbol: str,
        margin_type: str,
    ) -> dict[str, Any]:
        return {
            "symbol": symbol,
            "margin_type": margin_type,
        }

    async def close_all_positions(
        self,
        symbol: str | None = None,
    ) -> dict[str, Any]:
        return {"symbol": symbol, "closed": True}


def test_adapter_implements_base_exchange_contract() -> None:
    adapter = BingXAdapter(client=FakeBingXClient())

    assert isinstance(adapter, BaseExchange)
    assert adapter.exchange_name == "bingx"


def test_connect_disconnect_lifecycle_is_idempotent() -> None:
    client = FakeBingXClient()
    adapter = BingXAdapter(client=client)

    async def scenario() -> None:
        assert await adapter.health_check() is False
        await adapter.connect()
        await adapter.connect()
        assert adapter.is_connected is True
        assert await adapter.health_check() is True
        await adapter.disconnect()
        await adapter.disconnect()
        assert await adapter.health_check() is False

    run(scenario())

    assert client.server_time_calls == 2
    assert client.close_calls == 1


def test_factory_owned_client_is_recreated_after_disconnect() -> None:
    created: list[FakeBingXClient] = []

    def factory(**config: Any) -> FakeBingXClient:
        client = FakeBingXClient()
        created.append(client)
        return client

    adapter = BingXAdapter(client_factory=factory)

    async def scenario() -> None:
        await adapter.connect()
        await adapter.disconnect()
        await adapter.connect()

    run(scenario())

    assert len(created) == 2
    assert created[0].close_calls == 1
    assert adapter.client is created[1]


def test_injected_client_cannot_reconnect_after_close() -> None:
    adapter = BingXAdapter(client=FakeBingXClient())

    async def scenario() -> None:
        await adapter.connect()
        await adapter.disconnect()

        with pytest.raises(
            ExchangeError,
            match="cannot be reused",
        ):
            await adapter.connect()

    run(scenario())


def test_health_check_returns_false_on_runtime_failure() -> None:
    client = FakeBingXClient()
    adapter = BingXAdapter(client=client)

    async def scenario() -> None:
        await adapter.connect()
        client.server_error = RuntimeError("offline")
        assert await adapter.health_check() is False

    run(scenario())


def test_verify_connection_returns_safe_metadata() -> None:
    adapter = BingXAdapter(
        client=FakeBingXClient(demo_mode=True)
    )

    report = run(adapter.verify_connection())

    assert report == {
        "status": "connected",
        "exchange": "bingx",
        "server_time": 1_700_000_000_000,
        "demo_mode": True,
    }


def test_market_and_account_data_are_normalized() -> None:
    adapter = BingXAdapter(client=FakeBingXClient())

    async def scenario() -> None:
        balances = await adapter.fetch_balance()
        positions = await adapter.fetch_positions()
        ticker = await adapter.fetch_ticker("BTC-USDT")
        book = await adapter.fetch_orderbook("BTC-USDT")
        candles = await adapter.fetch_ohlcv(
            "BTC-USDT",
            "1h",
            limit=25,
        )

        assert balances["USDT"] == {
            "free": Decimal("80"),
            "used": Decimal("25"),
            "total": Decimal("105"),
            "wallet_balance": Decimal("100"),
            "unrealized_pnl": Decimal("5"),
            "max_withdraw_amount": Decimal("75"),
        }
        assert positions[0]["side"] == "short"
        assert positions[0]["contracts"] == Decimal("2")
        assert positions[0]["percentage"] == Decimal("10.00")
        assert ticker["last"] == Decimal("101")
        assert ticker["timestamp"] == 1_700_000_000_000
        assert book["nonce"] == 42
        assert book["spread"] == Decimal("1")
        assert candles == [
            [
                1_700_000_000_000,
                Decimal("100"),
                Decimal("110"),
                Decimal("90"),
                Decimal("105"),
                Decimal("10"),
            ]
        ]

    run(scenario())


def test_create_order_translates_and_caches_symbol() -> None:
    client = FakeBingXClient()
    adapter = BingXAdapter(client=client)

    order = run(
        adapter.create_order(
            "BTC-USDT",
            "limit",
            "buy",
            "2",
            "100",
            positionSide="LONG",
            timeInForce="IOC",
            stopLoss="90",
            takeProfit="120",
            clientOrderId="alpha-1",
        )
    )

    assert order["id"] == "order-1"
    assert order["remaining"] == Decimal("1.5")
    assert order["side"] == "buy"
    assert client.place_order_calls == [
        {
            "symbol": "BTC-USDT",
            "side": "BUY",
            "position_side": "LONG",
            "order_type": "LIMIT",
            "quantity": Decimal("2"),
            "price": Decimal("100"),
            "stop_price": None,
            "stop_loss": Decimal("90"),
            "take_profit": Decimal("120"),
            "time_in_force": "IOC",
            "client_order_id": "alpha-1",
        }
    ]

    cancel_result = run(adapter.cancel_order("order-1"))

    assert cancel_result["symbol"] == "BTC-USDT"
    assert client.cancel_order_calls == [
        ("BTC-USDT", "order-1")
    ]


def test_limit_order_requires_price() -> None:
    adapter = BingXAdapter(client=FakeBingXClient())

    with pytest.raises(
        ValueError,
        match="price is required",
    ):
        run(
            adapter.create_order(
                "BTC-USDT",
                "limit",
                "buy",
                "1",
            )
        )


def test_unsupported_order_parameter_is_rejected() -> None:
    client = FakeBingXClient()
    adapter = BingXAdapter(client=client)

    with pytest.raises(
        ValueError,
        match="reduceOnly",
    ):
        run(
            adapter.create_order(
                "BTC-USDT",
                "market",
                "sell",
                "1",
                reduceOnly=True,
            )
        )

    assert client.place_order_calls == []


def test_duplicate_parameter_alias_is_rejected() -> None:
    adapter = BingXAdapter(client=FakeBingXClient())

    with pytest.raises(
        ValueError,
        match="Use only one",
    ):
        run(
            adapter.create_order(
                "BTC-USDT",
                "market",
                "buy",
                "1",
                position_side="LONG",
                positionSide="LONG",
            )
        )


def test_cancel_order_can_resolve_symbol_from_open_orders() -> None:
    client = FakeBingXClient()
    client.open_orders = [
        make_order("order-2", "ETH-USDT")
    ]
    adapter = BingXAdapter(client=client)

    result = run(adapter.cancel_order("order-2"))

    assert result["symbol"] == "ETH-USDT"
    assert client.cancel_order_calls == [
        ("ETH-USDT", "order-2")
    ]


def test_unresolved_order_symbol_raises_typed_error() -> None:
    adapter = BingXAdapter(client=FakeBingXClient())

    with pytest.raises(OrderError) as captured:
        run(adapter.fetch_order("missing-order"))

    assert captured.value.operation == "resolve_order_symbol"


def test_fetch_order_uses_explicit_symbol_and_normalizes_result() -> None:
    client = FakeBingXClient()
    adapter = BingXAdapter(client=client)

    order = run(
        adapter.fetch_order(
            "order-1",
            "BTC-USDT",
        )
    )

    assert order["id"] == "order-1"
    assert order["status"] == "new"
    assert order["timestamp"] == 1_700_000_000_000
    assert client.get_order_calls == [
        ("BTC-USDT", "order-1")
    ]


def test_open_orders_populate_symbol_cache() -> None:
    client = FakeBingXClient()
    client.open_orders = [
        make_order("order-3", "SOL-USDT")
    ]
    adapter = BingXAdapter(client=client)

    orders = run(adapter.fetch_open_orders())

    assert orders[0]["symbol"] == "SOL-USDT"

    run(adapter.cancel_order("order-3"))

    assert client.cancel_order_calls == [
        ("SOL-USDT", "order-3")
    ]


def test_bingx_specific_market_helpers_are_normalized() -> None:
    adapter = BingXAdapter(client=FakeBingXClient())

    async def scenario() -> None:
        funding = await adapter.get_funding_rate("BTC-USDT")
        trades = await adapter.get_recent_trades(
            "BTC-USDT",
            10,
        )

        assert funding["funding_rate"] == Decimal("-0.0001")
        assert funding["funding_timestamp"] == (
            1_700_000_000_000
        )
        assert trades == [
            {
                "id": "7",
                "price": Decimal("100.5"),
                "amount": Decimal("0.25"),
                "side": "sell",
                "timestamp": 1_700_000_000_000,
                "datetime": datetime.fromtimestamp(
                    1_700_000_000,
                    tz=UTC,
                ).isoformat(),
            }
        ]

    run(scenario())


def test_compatibility_aliases_delegate_to_canonical_methods() -> None:
    adapter = BingXAdapter(client=FakeBingXClient())

    async def scenario() -> None:
        assert await adapter.get_balance() == (
            await adapter.fetch_balance()
        )
        assert await adapter.get_positions() == (
            await adapter.fetch_positions()
        )
        assert await adapter.get_ticker("BTC-USDT") == (
            await adapter.fetch_ticker("BTC-USDT")
        )
        assert await adapter.get_orderbook("BTC-USDT") == (
            await adapter.fetch_orderbook("BTC-USDT")
        )
        assert await adapter.get_ohlcv(
            "BTC-USDT",
            "1h",
            5,
        ) == await adapter.fetch_ohlcv(
            "BTC-USDT",
            "1h",
            5,
        )

    run(scenario())


def test_async_context_manager_uses_adapter_lifecycle() -> None:
    client = FakeBingXClient()
    adapter = BingXAdapter(client=client)

    async def scenario() -> None:
        async with adapter as active:
            assert active is adapter
            assert adapter.is_connected is True
            raise LookupError("body failed")

    with pytest.raises(LookupError, match="body failed"):
        run(scenario())

    assert client.close_calls == 1
    assert adapter.is_connected is False


@pytest.mark.parametrize(
    ("kwargs", "error_type", "message"),
    [
        (
            {"health_timeout": 0},
            ValueError,
            "health_timeout",
        ),
        (
            {"default_position_side": "invalid"},
            ValueError,
            "position_side",
        ),
        (
            {"client_factory": object()},
            TypeError,
            "client_factory",
        ),
    ],
)
def test_invalid_configuration_is_rejected(
    kwargs: dict[str, Any],
    error_type: type[Exception],
    message: str,
) -> None:
    with pytest.raises(error_type, match=message):
        BingXAdapter(**kwargs)


def test_injected_client_rejects_constructor_configuration() -> None:
    with pytest.raises(
        ValueError,
        match="cannot be supplied",
    ):
        BingXAdapter(
            api_key="unused",
            client=FakeBingXClient(),
        )


def test_incomplete_client_is_rejected() -> None:
    with pytest.raises(
        TypeError,
        match="missing required methods",
    ):
        BingXAdapter(client=object())  # type: ignore[arg-type]