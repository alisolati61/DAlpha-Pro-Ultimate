"""Behavioral tests for the BingX HTTP transport and parsers."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
from collections.abc import Mapping
from decimal import Decimal
from typing import Any
from urllib.parse import parse_qsl

import httpx
import pytest

from src.exchange.bingx_client import BingXHttpClient
from src.exchange.exceptions import (
    AuthenticationError,
    InsufficientFundsError,
    InvalidSymbolError,
    NetworkError,
    OrderError,
    RateLimitError,
)
from src.exchange.models import (
    BingXOrderSide,
    BingXOrderStatus,
    BingXOrderType,
    BingXPositionSide,
)
from src.exchange.ratelimiter import RateLimiter


def run(coroutine: Any) -> Any:
    return asyncio.run(coroutine)


def unlimited_rate_limiter() -> RateLimiter:
    return RateLimiter(1_000_000)


def build_client(
    transport: httpx.BaseTransport | httpx.AsyncBaseTransport,
    **kwargs: Any,
) -> tuple[BingXHttpClient, httpx.AsyncClient]:
    http_client = httpx.AsyncClient(transport=transport)
    client = BingXHttpClient(
        api_key="api-key",
        api_secret="api-secret",
        http_client=http_client,
        rate_limiter=unlimited_rate_limiter(),
        clock_ms=lambda: 1_700_000_000_000,
        **kwargs,
    )
    return client, http_client


def test_signed_request_uses_canonical_unencoded_signature() -> None:
    captured: dict[str, Any] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        return httpx.Response(
            200,
            json={"code": 0, "data": {"ok": True}},
            request=request,
        )

    client, http_client = build_client(
        httpx.MockTransport(handler)
    )
    original = {
        "symbol": "BTC-USDT",
        "quantity": Decimal("0.0100"),
        "reduceOnly": False,
    }

    response = run(
        client.request(
            "GET",
            "/openApi/swap/v2/user/positions",
            params=original,
        )
    )

    request = captured["request"]
    query = dict(parse_qsl(request.url.query.decode()))
    signing_params = {
        "quantity": "0.0100",
        "recvWindow": "5000",
        "reduceOnly": "false",
        "symbol": "BTC-USDT",
        "timestamp": "1700000000000",
    }
    signing_string = "&".join(
        f"{key}={value}"
        for key, value in sorted(signing_params.items())
    )
    expected_signature = hmac.new(
        b"api-secret",
        signing_string.encode(),
        hashlib.sha256,
    ).hexdigest()

    assert response == {"code": 0, "data": {"ok": True}}
    assert original == {
        "symbol": "BTC-USDT",
        "quantity": Decimal("0.0100"),
        "reduceOnly": False,
    }
    assert query == {
        **signing_params,
        "signature": expected_signature,
    }
    assert request.headers["X-BX-APIKEY"] == "api-key"
    assert request.headers["X-SOURCE-KEY"] == "BX-AI-SKILL"

    run(http_client.aclose())


def test_public_request_has_timestamp_without_credentials() -> None:
    captured: dict[str, Any] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        return httpx.Response(
            200,
            json={"code": 0, "data": {}},
            request=request,
        )

    http_client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    )
    client = BingXHttpClient(
        http_client=http_client,
        rate_limiter=unlimited_rate_limiter(),
        clock_ms=lambda: 123,
    )

    run(
        client.request(
            "GET",
            "/openApi/swap/v2/server/time",
            signed=False,
        )
    )

    request = captured["request"]
    query = dict(parse_qsl(request.url.query.decode()))

    assert query == {"timestamp": "123"}
    assert "X-BX-APIKEY" not in request.headers

    run(http_client.aclose())


def test_signed_request_requires_both_credentials() -> None:
    client = BingXHttpClient(
        api_key="key-only",
        rate_limiter=unlimited_rate_limiter(),
    )

    with pytest.raises(AuthenticationError) as captured:
        run(
            client.request(
                "GET",
                "/private",
                signed=True,
            )
        )

    assert captured.value.operation == "sign_request"


def test_network_retry_uses_official_fallback_domain() -> None:
    hosts: list[str] = []
    delays: list[float] = []

    async def sleep(delay: float) -> None:
        delays.append(delay)

    async def handler(request: httpx.Request) -> httpx.Response:
        hosts.append(request.url.host)

        if len(hosts) == 1:
            raise httpx.ConnectError(
                "primary offline",
                request=request,
            )

        return httpx.Response(
            200,
            json={"code": 0, "data": {"ok": True}},
            request=request,
        )

    client, http_client = build_client(
        httpx.MockTransport(handler),
        max_retries=1,
        retry_base_delay=0.25,
        retry_max_delay=1,
        sleep=sleep,
    )

    assert run(
        client.request("GET", "/public", signed=False)
    )["data"] == {"ok": True}
    assert hosts == [
        "open-api.bingx.com",
        "open-api.bingx.pro",
    ]
    assert delays == [0.25]

    run(http_client.aclose())


def test_mutating_request_is_not_retried_by_default() -> None:
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ReadTimeout("ambiguous write", request=request)

    client, http_client = build_client(
        httpx.MockTransport(handler),
        max_retries=5,
    )

    with pytest.raises(NetworkError):
        run(
            client.request(
                "POST",
                "/openApi/swap/v2/trade/order",
                params={"symbol": "BTC-USDT"},
            )
        )

    assert calls == 1
    run(http_client.aclose())


@pytest.mark.parametrize(
    ("code", "error_type"),
    [
        (100001, AuthenticationError),
        (100410, RateLimitError),
        (101204, InsufficientFundsError),
        (109425, InvalidSymbolError),
        (101400, OrderError),
    ],
)
def test_bingx_error_codes_are_translated(
    code: int,
    error_type: type[Exception],
) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "code": code,
                "msg": "rejected",
                "signature": "secret-signature",
            },
            request=request,
        )

    client, http_client = build_client(
        httpx.MockTransport(handler),
        max_retries=0,
    )

    with pytest.raises(error_type) as captured:
        run(client.request("GET", "/endpoint"))

    assert captured.value.exchange == "bingx"
    assert captured.value.raw_response["signature"] == "<redacted>"
    run(http_client.aclose())


def test_http_429_uses_retry_after_header() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429,
            headers={"Retry-After": "2.5"},
            json={"code": 100410},
            request=request,
        )

    client, http_client = build_client(
        httpx.MockTransport(handler),
        max_retries=0,
    )

    with pytest.raises(RateLimitError) as captured:
        run(client.request("GET", "/endpoint"))

    assert captured.value.retry_after == 2.5
    run(http_client.aclose())


def test_invalid_json_is_wrapped_without_response_body_leak() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=b"not-json secret=abc",
            request=request,
        )

    client, http_client = build_client(
        httpx.MockTransport(handler)
    )

    with pytest.raises(Exception) as captured:
        run(client.request("GET", "/endpoint", signed=False))

    assert "secret=abc" not in str(captured.value)
    run(http_client.aclose())


class StubClient(BingXHttpClient):
    def __init__(self, responses: list[dict[str, Any]]) -> None:
        super().__init__(
            api_key="key",
            api_secret="secret",
            rate_limiter=unlimited_rate_limiter(),
            clock_ms=lambda: 1,
        )
        self.responses = list(responses)
        self.calls: list[
            tuple[str, str, Mapping[str, Any] | None, bool]
        ] = []

    async def request(
        self,
        method: str,
        endpoint: str,
        params: Mapping[str, Any] | None = None,
        data: Mapping[str, Any] | None = None,
        signed: bool = True,
        *,
        weight: float = 1.0,
        retry_safe: bool | None = None,
    ) -> dict[str, Any]:
        self.calls.append((method, endpoint, params, signed))
        return self.responses.pop(0)


def test_market_parsers_create_validated_models() -> None:
    client = StubClient(
        [
            {
                "code": 0,
                "data": {
                    "symbol": "BTC-USDT",
                    "lastPrice": "101",
                    "priceChange": "1",
                    "priceChangePercent": "1",
                    "highPrice": "110",
                    "lowPrice": "90",
                    "volume": "5",
                    "quoteVolume": "500",
                    "bidPrice": "100",
                    "askPrice": "102",
                    "openTime": 1_700_000_000_000,
                    "closeTime": 1_700_086_400_000,
                },
            },
            {
                "code": 0,
                "data": {
                    "T": 42,
                    "bids": [["100", "2"], ["99", "1"]],
                    "asks": [["101", "3"]],
                },
            },
            {
                "code": 0,
                "data": [
                    [
                        1_700_000_000_000,
                        "100",
                        "110",
                        "90",
                        "105",
                        "10",
                        1_700_000_059_999,
                        "1000",
                        20,
                        "6",
                        "600",
                    ]
                ],
            },
        ]
    )

    async def scenario() -> None:
        ticker = await client.get_ticker("BTC-USDT")
        book = await client.get_orderbook("BTC-USDT")
        klines = await client.get_klines("BTC-USDT")

        assert ticker.last_price == Decimal("101")
        assert ticker.open_time is not None
        assert book.best_bid == Decimal("100")
        assert book.best_ask == Decimal("101")
        assert klines[0].high == Decimal("110")
        assert klines[0].close == Decimal("105")

    run(scenario())


def test_account_parsers_support_current_bingx_payloads() -> None:
    client = StubClient(
        [
            {
                "code": 0,
                "data": [
                    {
                        "asset": "USDT",
                        "balance": "100",
                        "equity": "105",
                        "unrealizedProfit": "5",
                        "availableMargin": "80",
                    }
                ],
            },
            {
                "code": 0,
                "data": [
                    {
                        "symbol": "BTC-USDT",
                        "positionSide": "SHORT",
                        "isolated": True,
                        "positionAmt": "0.1",
                        "avgPrice": "100",
                        "markPrice": "90",
                        "unrealizedProfit": "1",
                        "liquidationPrice": "150",
                        "leverage": 10,
                        "initialMargin": "1",
                    }
                ],
            },
        ]
    )

    async def scenario() -> None:
        balances = await client.get_balance()
        positions = await client.get_positions()

        assert balances[0].wallet_balance == Decimal("100")
        assert balances[0].margin_balance == Decimal("105")
        assert positions[0].position_side is BingXPositionSide.SHORT
        assert positions[0].margin_type == "ISOLATED"
        assert positions[0].entry_price == Decimal("100")

    run(scenario())


def test_place_order_is_non_retryable_and_parses_string_order_id() -> None:
    client = StubClient(
        [
            {
                "code": 0,
                "data": {
                    "orderID": "90071992547409931234",
                    "symbol": "BTC-USDT",
                    "side": "BUY",
                    "positionSide": "LONG",
                    "type": "LIMIT",
                    "status": "NEW",
                    "origQty": "0.1",
                    "price": "100",
                },
            }
        ]
    )

    order = run(
        client.place_order(
            symbol="BTC-USDT",
            side="BUY",
            position_side="LONG",
            order_type="LIMIT",
            quantity=Decimal("0.1"),
            price=Decimal("100"),
            client_order_id="alpha-1",
        )
    )

    assert order.order_id == "90071992547409931234"
    assert order.side is BingXOrderSide.BUY
    assert order.order_type is BingXOrderType.LIMIT
    assert order.status is BingXOrderStatus.NEW

    method, endpoint, params, signed = client.calls[0]
    assert method == "POST"
    assert endpoint == "/openApi/swap/v2/trade/order"
    assert signed is True
    assert params is not None
    assert params["clientOrderId"] == "alpha-1"


def test_demo_mode_uses_vst_primary_domain() -> None:
    client = BingXHttpClient(
        demo_mode=True,
        rate_limiter=unlimited_rate_limiter(),
    )

    assert client.base_url == "https://open-api-vst.bingx.com"


def test_custom_base_url_requires_https() -> None:
    with pytest.raises(ValueError, match="HTTPS"):
        BingXHttpClient(
            base_url="http://localhost:8000",
            rate_limiter=unlimited_rate_limiter(),
        )


def test_injected_http_client_is_not_closed_by_wrapper() -> None:
    async_client = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={"code": 0, "data": {}},
                request=request,
            )
        )
    )
    client = BingXHttpClient(
        http_client=async_client,
        rate_limiter=unlimited_rate_limiter(),
    )

    run(client.close())

    assert async_client.is_closed is False
    run(async_client.aclose())