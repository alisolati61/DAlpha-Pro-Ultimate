from __future__ import annotations

import json
import traceback
from decimal import Decimal
from typing import Any

import pytest

from src.exchange.bingx_client import BingXHttpClient
from src.exchange.exceptions import (
    AuthenticationError,
    ExchangeError,
    NetworkError,
    OrderError,
)
from src.exchange.models import BingXOrderBook
from src.vst_runtime import demo_transport
from src.vst_runtime.demo_order import (
    DemoAmbiguousSubmission,
    DemoCanaryError,
    DemoOrderPlan,
)
from src.vst_runtime.demo_transport import (
    BingXAsyncDemoOrderAdapter,
    create_async_demo_order_transport,
)
from src.vst_runtime.models import RemoteOrderStatus, VstConfiguration
from tests.unit.vst_runtime.test_demo_order import (
    NOW_MS,
    VST_HOST,
    FakeDemoTransport,
    balance,
    build_plan,
    position,
)


def remote_payload(
    plan: DemoOrderPlan,
    *,
    status: str = "NEW",
    filled: str = "0",
) -> dict[str, object]:
    return {
        "data": {
            "order": {
                "avgPrice": "0",
                "clientOrderId": plan.client_order_id,
                "executedQty": filled,
                "orderId": "exchange-order-1",
                "origQty": str(plan.quantity),
                "price": str(plan.limit_price),
                "reduceOnly": False,
                "side": plan.side,
                "status": status,
                "symbol": plan.symbol,
                "type": "LIMIT",
                "updateTime": NOW_MS,
            }
        }
    }


class RecordingBingXClient(BingXHttpClient):
    def __init__(self) -> None:
        super().__init__(
            api_key="vst-key",
            api_secret="vst-secret",
            demo_mode=True,
            base_url=VST_HOST,
            max_retries=0,
        )
        self.calls: list[
            tuple[str, str, dict[str, Any] | None, bool, bool | None]
        ] = []
        self.responses: dict[str, dict[str, object]] = {}
        self.request_error: Exception | None = None
        self.closed_by_adapter = False
        self.symbols: list[dict[str, object]] = [
            {
                "apiStateOpen": "true",
                "pricePrecision": 1,
                "quantityPrecision": 3,
                "status": 1,
                "symbol": "BTC-USDT",
                "tradeMinQuantity": "0.001",
                "tradeMinUSDT": "1",
            }
        ]
        self.book = BingXOrderBook(
            "BTC-USDT",
            123,
            [(Decimal("99"), Decimal("1"))],
            [(Decimal("101"), Decimal("1"))],
        )

    async def get_symbols(self) -> list[dict[str, Any]]:
        return self.symbols

    async def get_orderbook(
        self, symbol: str, limit: int = 20
    ) -> BingXOrderBook:
        self.calls.append(("GET_BOOK", symbol, {"limit": limit}, False, None))
        return self.book

    async def get_balance(self) -> list[Any]:
        return [balance()]

    async def get_positions(self, symbol: str | None = None) -> list[Any]:
        return [position()]

    async def request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        *,
        signed: bool = False,
        retry_safe: bool | None = None,
    ) -> dict[str, Any]:
        self.calls.append((method, path, params, signed, retry_safe))
        if self.request_error is not None:
            raise self.request_error
        return self.responses[path]  # type: ignore[return-value]

    async def close(self) -> None:
        self.closed_by_adapter = True


def configuration(**changes: Any) -> VstConfiguration:
    values: dict[str, Any] = {
        "api_key": "vst-key",
        "api_secret": "vst-secret",
        "symbols": frozenset({"BTC-USDT"}),
        "maximum_order_notional": Decimal("10"),
        "maximum_open_positions": 1,
        "maximum_session_loss": Decimal("10"),
        "maximum_exposure": Decimal("10"),
        "configuration_version": "demo-test-v1",
        "base_url": VST_HOST,
    }
    values.update(changes)
    return VstConfiguration(**values)


@pytest.mark.asyncio
async def test_adapter_read_mapping_and_official_read_paths() -> None:
    client = RecordingBingXClient()
    client.responses = {
        "/openApi/swap/v2/trade/leverage": {
            "data": {"longLeverage": 1, "shortLeverage": 2}
        },
        "/openApi/swap/v1/positionSide/dual": {
            "data": {"dualSidePosition": True}
        },
        "/openApi/swap/v2/trade/openOrders": {"data": {"orders": []}},
        "/openApi/swap/v2/trade/allOrders": {"data": {"orders": []}},
    }
    adapter = BingXAsyncDemoOrderAdapter(client)

    contract = await adapter.fetch_constraints("btc-usdt")
    book = await adapter.fetch_orderbook("btc-usdt")
    assert contract.symbol == "BTC-USDT"
    assert contract.price_tick == Decimal("0.1")
    assert contract.quantity_step == Decimal("0.001")
    assert contract.minimum_quantity == Decimal("0.001")
    assert contract.minimum_notional == Decimal("1")
    assert contract.maximum_long_leverage == 2
    assert contract.maximum_short_leverage == 2
    assert contract.trading_enabled
    assert (book.best_bid, book.best_ask, book.update_id) == (
        Decimal("99"),
        Decimal("101"),
        "123",
    )
    assert tuple(await adapter.fetch_balances()) == (balance(),)
    assert tuple(await adapter.fetch_positions("BTC-USDT")) == (position(),)
    assert (await adapter.fetch_leverage("BTC-USDT")).long_leverage == 1
    assert await adapter.fetch_position_mode() == "HEDGE"
    assert tuple(await adapter.fetch_open_orders("BTC-USDT")) == ()
    assert tuple(await adapter.fetch_recent_orders("BTC-USDT")) == ()

    assert client.calls == [
        ("GET_BOOK", "BTC-USDT", {"limit": 5}, False, None),
        (
            "GET",
            "/openApi/swap/v2/trade/leverage",
            {"symbol": "BTC-USDT"},
            True,
            None,
        ),
        (
            "GET",
            "/openApi/swap/v1/positionSide/dual",
            None,
            True,
            None,
        ),
        (
            "GET",
            "/openApi/swap/v2/trade/openOrders",
            {"symbol": "BTC-USDT"},
            True,
            None,
        ),
        (
            "GET",
            "/openApi/swap/v2/trade/allOrders",
            {"symbol": "BTC-USDT", "limit": 1_000},
            True,
            None,
        ),
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("extra_fields"),
    (
        {},
        {"maxLongLeverage": None, "maxShortLeverage": "not-authoritative"},
    ),
)
async def test_official_vst_contract_uses_the_fixed_canary_leverage_cap(
    extra_fields: dict[str, object],
) -> None:
    client = RecordingBingXClient()
    client.symbols[0].update(extra_fields)
    adapter = BingXAsyncDemoOrderAdapter(client)

    constraints = await adapter.fetch_constraints("BTC-USDT")

    assert constraints.maximum_long_leverage == 2
    assert constraints.maximum_short_leverage == 2
    assert constraints.trading_enabled
    assert client.calls == []


@pytest.mark.asyncio
async def test_submit_uses_one_limit_write_with_compact_structured_protection() -> None:
    plan = await build_plan(FakeDemoTransport())
    client = RecordingBingXClient()
    client.responses["/openApi/swap/v2/trade/order"] = remote_payload(plan)
    adapter = BingXAsyncDemoOrderAdapter(client)

    order = await adapter.submit_protected_limit(plan)

    assert order.client_order_id == plan.client_order_id
    assert order.status is RemoteOrderStatus.NEW
    assert len(client.calls) == 1
    method, path, params, signed, retry_safe = client.calls[0]
    assert (method, path, signed, retry_safe) == (
        "POST",
        "/openApi/swap/v2/trade/order",
        True,
        False,
    )
    assert params is not None
    assert set(params) == {
        "clientOrderId",
        "positionSide",
        "price",
        "quantity",
        "side",
        "stopLoss",
        "symbol",
        "takeProfit",
        "timeInForce",
        "type",
    }
    assert params["clientOrderId"] == plan.client_order_id
    assert params["positionSide"] == plan.position_side
    assert params["type"] == "LIMIT"
    assert params["timeInForce"] == "PostOnly"
    assert params["stopLoss"] == (
        '{"stopGuaranteed":false,"stopPrice":90,'
        '"type":"STOP_MARKET","workingType":"MARK_PRICE"}'
    )
    assert params["takeProfit"] == (
        '{"stopGuaranteed":false,"stopPrice":110,'
        '"type":"TAKE_PROFIT_MARKET","workingType":"MARK_PRICE"}'
    )
    assert json.loads(params["stopLoss"])["type"] == "STOP_MARKET"
    assert json.loads(params["takeProfit"])["type"] == "TAKE_PROFIT_MARKET"


@pytest.mark.asyncio
async def test_query_and_cancel_use_only_client_order_id_and_symbol() -> None:
    plan = await build_plan(FakeDemoTransport())
    client = RecordingBingXClient()
    client.responses["/openApi/swap/v2/trade/order"] = remote_payload(
        plan, status="CANCELLED"
    )
    adapter = BingXAsyncDemoOrderAdapter(client)

    queried = await adapter.query_order(plan.symbol, plan.client_order_id)
    cancelled = await adapter.cancel_order(plan.symbol, plan.client_order_id)

    assert queried is not None and queried.status is RemoteOrderStatus.CANCELED
    assert cancelled is not None and cancelled.status is RemoteOrderStatus.CANCELED
    expected_params = {
        "clientOrderId": plan.client_order_id,
        "symbol": plan.symbol,
    }
    assert client.calls == [
        (
            "GET",
            "/openApi/swap/v2/trade/order",
            expected_params,
            True,
            None,
        ),
        (
            "DELETE",
            "/openApi/swap/v2/trade/order",
            expected_params,
            True,
            False,
        ),
    ]
    assert "orderId" not in expected_params


@pytest.mark.asyncio
async def test_query_maps_only_official_not_found_to_absent() -> None:
    client = RecordingBingXClient()
    client.request_error = OrderError(
        "fake not found", exchange="bingx", error_code="109421"
    )
    adapter = BingXAsyncDemoOrderAdapter(client)
    assert await adapter.query_order("BTC-USDT", "dalphavst123") is None

    client.request_error = OrderError(
        "fake rejection", exchange="bingx", error_code="100001"
    )
    with pytest.raises(DemoCanaryError, match="exchange_read_rejected"):
        await adapter.query_order("BTC-USDT", "dalphavst123")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "expected_type", "reason"),
    [
        (NetworkError("fake network", "bingx"), DemoAmbiguousSubmission, None),
        (
            OrderError(
                "fake duplicate",
                "bingx",
                error_code="101481",
            ),
            DemoAmbiguousSubmission,
            None,
        ),
        (
            AuthenticationError("fake auth", "bingx"),
            DemoCanaryError,
            "authentication_rejected",
        ),
        (
            ExchangeError("fake rejected", "bingx"),
            DemoAmbiguousSubmission,
            None,
        ),
        (
            OrderError(
                "fake rejected",
                "bingx",
                error_code="109400",
            ),
            DemoCanaryError,
            "order_rejected",
        ),
    ],
)
async def test_submit_failure_mapping_is_sanitized_and_never_retried(
    error: Exception,
    expected_type: type[Exception],
    reason: str | None,
) -> None:
    plan = await build_plan(FakeDemoTransport())
    client = RecordingBingXClient()
    client.request_error = error
    adapter = BingXAsyncDemoOrderAdapter(client)

    with pytest.raises(expected_type) as captured:
        await adapter.submit_protected_limit(plan)
    if reason is not None:
        assert isinstance(captured.value, DemoCanaryError)
        assert captured.value.reason_code == reason
    assert len(client.calls) == 1
    assert client.calls[0][4] is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method_name", "path"),
    [
        ("fetch_open_orders", "/openApi/swap/v2/trade/openOrders"),
        ("fetch_recent_orders", "/openApi/swap/v2/trade/allOrders"),
    ],
)
async def test_order_collections_require_authoritative_data_container(
    method_name: str,
    path: str,
) -> None:
    client = RecordingBingXClient()
    client.responses[path] = {}
    adapter = BingXAsyncDemoOrderAdapter(client)

    with pytest.raises(DemoCanaryError, match="invalid_response_schema"):
        await getattr(adapter, method_name)("BTC-USDT")


@pytest.mark.asyncio
async def test_post_dispatch_response_schema_uncertainty_is_ambiguous() -> None:
    plan = await build_plan(FakeDemoTransport())
    client = RecordingBingXClient()
    client.responses["/openApi/swap/v2/trade/order"] = {"data": {}}
    adapter = BingXAsyncDemoOrderAdapter(client)

    with pytest.raises(DemoAmbiguousSubmission):
        await adapter.submit_protected_limit(plan)
    assert len(client.calls) == 1
    assert client.calls[0][0] == "POST"
    assert client.calls[0][4] is False


def test_adapter_public_surface_has_no_unapproved_write_or_raw_client_escape() -> None:
    adapter = BingXAsyncDemoOrderAdapter(RecordingBingXClient())
    public = {name for name in dir(adapter) if not name.startswith("_")}
    assert public == {
        "cancel_order",
        "close",
        "fetch_balances",
        "fetch_constraints",
        "fetch_leverage",
        "fetch_open_orders",
        "fetch_orderbook",
        "fetch_position_mode",
        "fetch_positions",
        "fetch_recent_orders",
        "query_order",
        "selected_host",
        "submit_protected_limit",
    }
    assert public.isdisjoint(
        {
            "amend_order",
            "cancel_all_orders",
            "close_all_positions",
            "create_market_order",
            "request",
            "set_leverage",
            "transfer",
            "withdraw",
        }
    )
    assert adapter.selected_host == VST_HOST


@pytest.mark.asyncio
async def test_close_delegates_and_factory_wraps_existing_client_without_io() -> None:
    client = RecordingBingXClient()
    adapter = BingXAsyncDemoOrderAdapter(client)
    await adapter.close()
    assert client.closed_by_adapter

    concrete = create_async_demo_order_transport(
        configuration(), selected_host="https://open-api-vst.bingx.pro"
    )
    assert isinstance(concrete, BingXAsyncDemoOrderAdapter)
    wrapped = concrete._BingXAsyncDemoOrderAdapter__client
    assert isinstance(wrapped, BingXHttpClient)
    assert wrapped._base_urls == ("https://open-api-vst.bingx.pro",)
    await concrete.close()


def test_factory_rejects_non_vst_host_before_client_construction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created: list[str] = []

    def forbidden_client(*args: object, **kwargs: object) -> None:
        created.append("client")

    monkeypatch.setattr(demo_transport, "BingXHttpClient", forbidden_client)
    with pytest.raises(DemoCanaryError, match="selected_host_not_vst"):
        create_async_demo_order_transport(
            configuration(), selected_host="https://open-api.bingx.com"
        )
    assert created == []


@pytest.mark.asyncio
async def test_sanitized_failures_suppress_remote_and_credential_context() -> None:
    client = RecordingBingXClient()
    client.request_error = ExchangeError(
        "vst-secret signature=secret-signature raw-secret",
        exchange="bingx",
        raw_response={"apiKey": "vst-key", "secret": "vst-secret"},
    )
    adapter = BingXAsyncDemoOrderAdapter(client)

    with pytest.raises(DemoCanaryError) as captured:
        await adapter.fetch_position_mode()

    rendered = "".join(traceback.format_exception(captured.value))
    rendered += repr(captured.value)
    assert "vst-key" not in rendered
    assert "vst-secret" not in rendered
    assert "secret-signature" not in rendered
    assert "raw-secret" not in rendered
    assert captured.value.reason_code == "exchange_read_rejected"
    assert captured.value.__cause__ is None
    assert captured.value.__context__ is None
