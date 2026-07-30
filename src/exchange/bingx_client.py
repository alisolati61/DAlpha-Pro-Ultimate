"""Asynchronous BingX perpetual-futures HTTP client.

The client owns request signing, transport lifecycle, bounded retries, rate
limiting, error translation, and normalization into BingX boundary models.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import math
import os
import socket
import ssl
import time
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from types import TracebackType
from typing import Any, Self
from urllib.parse import quote, urlsplit

import httpx

from src.exchange.exceptions import (
    AuthenticationError,
    ExchangeError,
    ExchangeNotAvailableError,
    InsufficientFundsError,
    InvalidSymbolError,
    NetworkError,
    OrderError,
    RateLimitError,
)
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
from src.exchange.ratelimiter import RateLimiter

ClockMilliseconds = Callable[[], int]
AsyncSleeper = Callable[[float], Awaitable[None]]

_DEFAULT_REQUEST_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "DAlpha-Pro-Ultimate/1.0",
}
_PROTECTED_REQUEST_HEADERS = frozenset({"authorization", "x-bx-apikey"})
_LIVE_BASE_URLS = (
    "https://open-api.bingx.com",
    "https://open-api.bingx.pro",
)
_VST_BASE_URLS = (
    "https://open-api-vst.bingx.com",
    "https://open-api-vst.bingx.pro",
)

_AUTHENTICATION_CODES = {
    100001,
    100004,
    100412,
    100413,
    100419,
    100421,
}
_RATE_LIMIT_CODES = {100410, 100429}
_INSUFFICIENT_FUNDS_CODES = {80014, 101204, 101206}
_INVALID_SYMBOL_CODES = {109425}
_UNAVAILABLE_CODES = {100500, 109500, 110500}
_ORDER_CODES = {
    101211,
    101400,
    101415,
    101419,
    101481,
    104103,
    109400,
    109421,
    110206,
    110400,
}
_DNS_ERRNOS = frozenset({-3, -2, 8, 11001})
_CONNECTION_REFUSED_ERRNOS = frozenset({61, 111, 10061})
_CONNECTION_RESET_ERRNOS = frozenset({54, 104, 10054})
_CONNECT_TIMEOUT_ERRNOS = frozenset({60, 110, 10060})


@dataclass(frozen=True, slots=True)
class BingXTransportDiagnostic:
    """Sanitized details for one public transport outcome."""

    attempted_host: str
    transport_stage: str
    exception_type: str | None
    sanitized_errno: int | None
    reason_code: str
    server_time_ms: int | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class BingXTransportError(NetworkError):
    """Network failure with safe machine-readable transport diagnostics."""

    def __init__(
        self,
        *,
        diagnostic: BingXTransportDiagnostic,
        operation: str,
    ) -> None:
        super().__init__(
            message="BingX transport request failed.",
            exchange="bingx",
            operation=operation,
        )
        self.attempted_host = diagnostic.attempted_host
        self.transport_stage = diagnostic.transport_stage
        self.exception_type = diagnostic.exception_type
        self.sanitized_errno = diagnostic.sanitized_errno
        self.reason_code = diagnostic.reason_code

    def to_dict(
        self,
        *,
        include_raw_response: bool = False,
    ) -> dict[str, object]:
        payload = super().to_dict(include_raw_response=include_raw_response)
        payload.update(
            {
                "attempted_host": self.attempted_host,
                "transport_stage": self.transport_stage,
                "exception_type": self.exception_type,
                "sanitized_errno": self.sanitized_errno,
                "reason_code": self.reason_code,
            }
        )
        return payload


class BingXHttpClient:
    """Low-level client for BingX USDT-M perpetual REST endpoints.

    Mutating requests are never retried automatically unless ``retry_safe`` is
    explicitly set. This prevents duplicate live orders after ambiguous network
    failures.
    """

    def __init__(
        self,
        api_key: str | None = None,
        api_secret: str | None = None,
        demo_mode: bool | None = None,
        base_url: str | None = None,
        *,
        recv_window: int = 5_000,
        timeout: float = 10.0,
        max_retries: int = 2,
        retry_base_delay: float = 0.5,
        retry_max_delay: float = 5.0,
        requests_per_second: float = 10.0,
        source_key: str | None = "BX-AI-SKILL",
        http_client: httpx.AsyncClient | None = None,
        rate_limiter: RateLimiter | None = None,
        clock_ms: ClockMilliseconds | None = None,
        sleep: AsyncSleeper = asyncio.sleep,
    ) -> None:
        self.api_key = self._optional_secret(
            api_key,
            environment_name="BINGX_API_KEY",
        )
        self.api_secret = self._optional_secret(
            api_secret,
            environment_name="BINGX_API_SECRET",
        )
        self.demo_mode = bool(demo_mode)

        self._base_urls: tuple[str, ...]
        if base_url is None:
            self._base_urls = _VST_BASE_URLS if self.demo_mode else _LIVE_BASE_URLS
        else:
            self._base_urls = (self._validate_base_url(base_url),)

        self.base_url = self._base_urls[0]
        self.last_attempted_base_url = self.base_url
        self.recv_window = self._validate_integer(
            recv_window,
            field_name="recv_window",
            minimum=1,
            maximum=5_000,
        )
        self.timeout = self._validate_positive_number(
            timeout,
            field_name="timeout",
        )
        self.max_retries = self._validate_integer(
            max_retries,
            field_name="max_retries",
            minimum=0,
        )
        self.retry_base_delay = self._validate_non_negative_number(
            retry_base_delay,
            field_name="retry_base_delay",
        )
        self.retry_max_delay = self._validate_non_negative_number(
            retry_max_delay,
            field_name="retry_max_delay",
        )

        if self.retry_max_delay < self.retry_base_delay:
            raise ValueError(
                "retry_max_delay must be greater than or equal to " "retry_base_delay."
            )

        if source_key is not None:
            source_key = self._required_text(
                source_key,
                field_name="source_key",
            )

        if not callable(sleep):
            raise TypeError("sleep must be callable.")

        if clock_ms is not None and not callable(clock_ms):
            raise TypeError("clock_ms must be callable or None.")

        self.source_key = source_key
        self._sleep = sleep
        self._clock_ms = clock_ms or (lambda: time.time_ns() // 1_000_000)
        self._rate_limiter = rate_limiter or RateLimiter(requests_per_second)

        self._client = http_client
        self._owns_client = http_client is None
        self._client_lock = asyncio.Lock()
        self._closed = False

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
        headers: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        """Execute one JSON request and return the validated response object."""

        normalized_method = self._normalize_method(method)
        normalized_endpoint = self._normalize_endpoint(endpoint)

        if signed and data:
            raise ValueError(
                "Signed BingX requests must use query parameters in this "
                "client. JSON-body signing is intentionally unsupported."
            )

        request_params = self._normalize_params(params)
        request_data = None if data is None else self._normalize_params(data)

        # Current BingX swap endpoints require a millisecond timestamp.
        request_params.setdefault("timestamp", str(self._timestamp_ms()))

        request_headers = dict(_DEFAULT_REQUEST_HEADERS)
        if headers is not None:
            for name, value in headers.items():
                normalized_name = self._required_text(
                    name,
                    field_name="header name",
                )
                if normalized_name.casefold() in _PROTECTED_REQUEST_HEADERS:
                    raise ValueError("credential headers cannot be overridden")
                request_headers[normalized_name] = self._required_text(
                    value,
                    field_name="header value",
                )

        if self.source_key is not None:
            request_headers["X-SOURCE-KEY"] = self.source_key

        if signed:
            self._require_credentials()
            request_params.setdefault(
                "recvWindow",
                str(self.recv_window),
            )
            signing_string = self._build_signing_string(request_params)
            request_params["signature"] = self._generate_signature(signing_string)
            request_headers["X-BX-APIKEY"] = self.api_key or ""

        if retry_safe is None:
            retry_safe = normalized_method in {"GET", "HEAD", "OPTIONS"}

        attempts = 1 + (self.max_retries if retry_safe else 0)
        last_error: ExchangeError | None = None

        for attempt_index in range(attempts):
            await self._rate_limiter.acquire(weight)
            base_url = self._base_urls[min(attempt_index, len(self._base_urls) - 1)]
            self.last_attempted_base_url = base_url
            url = self._build_url(
                base_url,
                normalized_endpoint,
                request_params,
            )

            try:
                response = await self._send(
                    normalized_method,
                    url,
                    headers=request_headers,
                    data=request_data,
                )
                payload = self._decode_response(
                    response,
                    operation=(f"{normalized_method} {normalized_endpoint}"),
                    signed=signed,
                )
                self._raise_for_error_payload(
                    payload,
                    status_code=response.status_code,
                    operation=(f"{normalized_method} {normalized_endpoint}"),
                )
                return payload
            except asyncio.CancelledError:
                raise
            except ExchangeError as exc:
                last_error = exc

                if attempt_index + 1 >= attempts or not exc.retryable:
                    raise

                await self._sleep(self._retry_delay(attempt_index, exc))
            except httpx.TimeoutException as exc:
                operation = f"{normalized_method} {normalized_endpoint}"
                last_error = BingXTransportError(
                    diagnostic=classify_transport_exception(
                        exc,
                        attempted_host=base_url,
                    ),
                    operation=operation,
                )

                if attempt_index + 1 >= attempts:
                    raise last_error from exc

                await self._sleep(self._retry_delay(attempt_index, last_error))
            except httpx.TransportError as exc:
                operation = f"{normalized_method} {normalized_endpoint}"
                last_error = BingXTransportError(
                    diagnostic=classify_transport_exception(
                        exc,
                        attempted_host=base_url,
                    ),
                    operation=operation,
                )

                if attempt_index + 1 >= attempts:
                    raise last_error from exc

                await self._sleep(self._retry_delay(attempt_index, last_error))

        assert last_error is not None
        raise last_error

    async def close(self) -> None:
        """Close an internally-owned HTTP client exactly once."""

        async with self._client_lock:
            if self._closed:
                return

            if (
                self._owns_client
                and self._client is not None
                and not self._client.is_closed
            ):
                await self._client.aclose()

            self._closed = True

    async def __aenter__(self) -> Self:
        await self._get_client()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        await self.close()
        return False

    async def get_server_time(self) -> int:
        response = await self.request(
            "GET",
            "/openApi/swap/v2/server/time",
            signed=False,
        )
        data = self._mapping_data(response)
        return self._validate_integer(
            data.get("serverTime"),
            field_name="serverTime",
            minimum=0,
        )

    async def diagnose_server_time(self) -> BingXTransportDiagnostic:
        """Run the public v2 server-time path and return only safe diagnostics."""

        try:
            server_time = await self.get_server_time()
        except Exception as exc:
            return classify_transport_exception(
                exc,
                attempted_host=self.last_attempted_base_url,
            )
        return BingXTransportDiagnostic(
            attempted_host=_sanitized_host(self.last_attempted_base_url),
            transport_stage="complete",
            exception_type=None,
            sanitized_errno=None,
            reason_code="ok",
            server_time_ms=server_time,
        )

    async def get_symbols(self) -> list[dict[str, Any]]:
        response = await self.request(
            "GET",
            "/openApi/swap/v2/quote/contracts",
            signed=False,
        )
        return [
            dict(item)
            for item in self._sequence_data(response)
            if isinstance(item, Mapping)
        ]

    async def get_ticker(self, symbol: str) -> BingXTicker:
        normalized_symbol = self._required_text(
            symbol,
            field_name="symbol",
        )
        response = await self.request(
            "GET",
            "/openApi/swap/v2/quote/ticker",
            params={"symbol": normalized_symbol},
            signed=False,
        )
        item = self._single_mapping_data(response)

        return BingXTicker(
            symbol=item.get("symbol", normalized_symbol),
            last_price=item.get("lastPrice", 0),
            price_change=item.get("priceChange", 0),
            price_change_percent=item.get(
                "priceChangePercent",
                0,
            ),
            high_price=item.get("highPrice", 0),
            low_price=item.get("lowPrice", 0),
            volume=item.get("volume", 0),
            quote_volume=item.get("quoteVolume", 0),
            bid_price=item.get("bidPrice", 0),
            ask_price=item.get("askPrice", 0),
            open_time=item.get("openTime"),
            close_time=item.get("closeTime"),
        )

    async def get_orderbook(
        self,
        symbol: str,
        limit: int = 20,
    ) -> BingXOrderBook:
        normalized_symbol = self._required_text(
            symbol,
            field_name="symbol",
        )
        normalized_limit = self._validate_integer(
            limit,
            field_name="limit",
            minimum=1,
            maximum=1_000,
        )
        response = await self.request(
            "GET",
            "/openApi/swap/v2/quote/depth",
            params={
                "symbol": normalized_symbol,
                "limit": normalized_limit,
            },
            signed=False,
        )
        data = self._mapping_data(response)

        return BingXOrderBook(
            symbol=normalized_symbol,
            last_update_id=data.get(
                "lastUpdateId",
                data.get("T", 0),
            ),
            bids=list(data.get("bids", [])),
            asks=list(data.get("asks", [])),
        )

    async def get_klines(
        self,
        symbol: str,
        interval: str = "1h",
        limit: int = 500,
        start_time: int | None = None,
        end_time: int | None = None,
    ) -> list[BingXKline]:
        params: dict[str, Any] = {
            "symbol": self._required_text(
                symbol,
                field_name="symbol",
            ),
            "interval": self._required_text(
                interval,
                field_name="interval",
            ),
            "limit": self._validate_integer(
                limit,
                field_name="limit",
                minimum=1,
                maximum=1_440,
            ),
        }

        if start_time is not None:
            params["startTime"] = self._validate_integer(
                start_time,
                field_name="start_time",
                minimum=0,
            )

        if end_time is not None:
            params["endTime"] = self._validate_integer(
                end_time,
                field_name="end_time",
                minimum=0,
            )

        response = await self.request(
            "GET",
            "/openApi/swap/v3/quote/klines",
            params=params,
            signed=False,
        )

        return [self._parse_kline(item) for item in self._sequence_data(response)]

    async def get_recent_trades(
        self,
        symbol: str,
        limit: int = 100,
    ) -> list[BingXTrade]:
        normalized_symbol = self._required_text(
            symbol,
            field_name="symbol",
        )
        response = await self.request(
            "GET",
            "/openApi/swap/v2/quote/trades",
            params={
                "symbol": normalized_symbol,
                "limit": self._validate_integer(
                    limit,
                    field_name="limit",
                    minimum=1,
                    maximum=1_000,
                ),
            },
            signed=False,
        )

        trades: list[BingXTrade] = []

        for item in self._sequence_data(response):
            if not isinstance(item, Mapping):
                raise ExchangeError(
                    message="BingX trade payload is malformed.",
                    exchange="bingx",
                    operation="parse_recent_trades",
                )

            side = item.get("side")

            if side is None:
                side = "SELL" if bool(item.get("buyerMaker", False)) else "BUY"

            trades.append(
                BingXTrade(
                    trade_id=item.get("id", 0),
                    price=item.get("price", 0),
                    quantity=item.get("qty", 0),
                    side=side,
                    timestamp=item.get("time", 0),
                )
            )

        return trades

    async def get_funding_rate(
        self,
        symbol: str,
    ) -> BingXFundingRate:
        normalized_symbol = self._required_text(
            symbol,
            field_name="symbol",
        )
        response = await self.request(
            "GET",
            "/openApi/swap/v2/quote/premiumIndex",
            params={"symbol": normalized_symbol},
            signed=False,
        )
        item = self._single_mapping_data(response)

        return BingXFundingRate(
            symbol=item.get("symbol", normalized_symbol),
            funding_rate=item.get(
                "lastFundingRate",
                item.get("fundingRate", 0),
            ),
            funding_time=item.get(
                "nextFundingTime",
                item.get("fundingTime", 0),
            ),
            mark_price=item.get("markPrice", 0),
        )

    async def get_balance(self) -> list[BingXBalance]:
        response = await self.request(
            "GET",
            "/openApi/swap/v3/user/balance",
            signed=True,
        )
        data = response.get("data", [])
        items: Sequence[Any]

        if isinstance(data, Mapping):
            nested = data.get("balance", data)

            if isinstance(nested, Mapping):
                items = [nested]
            elif isinstance(nested, Sequence) and not isinstance(
                nested,
                (str, bytes, bytearray),
            ):
                items = nested
            else:
                items = []
        elif isinstance(data, Sequence) and not isinstance(
            data,
            (str, bytes, bytearray),
        ):
            items = data
        else:
            items = []

        balances: list[BingXBalance] = []

        for item in items:
            if not isinstance(item, Mapping):
                raise ExchangeError(
                    message="BingX balance payload is malformed.",
                    exchange="bingx",
                    operation="parse_balance",
                )

            wallet_balance = item.get(
                "balance",
                item.get("walletBalance", 0),
            )
            unrealized_pnl = item.get("unrealizedProfit", 0)
            margin_balance = item.get(
                "equity",
                item.get(
                    "marginBalance",
                    Decimal(str(wallet_balance)) + Decimal(str(unrealized_pnl)),
                ),
            )
            available = item.get(
                "availableMargin",
                item.get("availableBalance", 0),
            )

            balances.append(
                BingXBalance(
                    asset=item.get("asset", "USDT"),
                    wallet_balance=wallet_balance,
                    unrealized_pnl=unrealized_pnl,
                    margin_balance=margin_balance,
                    available_balance=available,
                    max_withdraw_amount=item.get(
                        "maxWithdrawAmount",
                        available,
                    ),
                )
            )

        return balances

    async def get_positions(
        self,
        symbol: str | None = None,
    ) -> list[BingXPosition]:
        params: dict[str, Any] = {}

        if symbol is not None:
            params["symbol"] = self._required_text(
                symbol,
                field_name="symbol",
            )

        response = await self.request(
            "GET",
            "/openApi/swap/v2/user/positions",
            params=params,
            signed=True,
        )
        positions: list[BingXPosition] = []

        for item in self._sequence_data(response):
            if not isinstance(item, Mapping):
                raise ExchangeError(
                    message="BingX position payload is malformed.",
                    exchange="bingx",
                    operation="parse_positions",
                )

            isolated = item.get("isolated")
            margin_type = item.get("marginType")

            if margin_type is None and isinstance(isolated, bool):
                margin_type = "ISOLATED" if isolated else "CROSSED"

            entry_price = item.get(
                "avgPrice",
                item.get("entryPrice", 0),
            )

            positions.append(
                BingXPosition(
                    symbol=item.get("symbol", ""),
                    position_side=item.get(
                        "positionSide",
                        "BOTH",
                    ),
                    position_amount=item.get(
                        "positionAmt",
                        0,
                    ),
                    entry_price=entry_price,
                    mark_price=item.get(
                        "markPrice",
                        entry_price,
                    ),
                    unrealized_pnl=item.get(
                        "unrealizedProfit",
                        0,
                    ),
                    liquidation_price=item.get(
                        "liquidationPrice",
                        0,
                    ),
                    leverage=item.get("leverage", 1),
                    margin_type=margin_type or "CROSSED",
                    isolated_margin=(
                        item.get("isolatedMargin")
                        if item.get("isolatedMargin") is not None
                        else (item.get("initialMargin") if isolated else None)
                    ),
                )
            )

        return positions

    async def place_order(
        self,
        symbol: str,
        side: str,
        position_side: str,
        order_type: str,
        quantity: Decimal,
        price: Decimal | None = None,
        stop_price: Decimal | None = None,
        stop_loss: Decimal | None = None,
        take_profit: Decimal | None = None,
        time_in_force: str = "GTC",
        client_order_id: str | None = None,
    ) -> BingXOrder:
        params: dict[str, Any] = {
            "symbol": self._required_text(
                symbol,
                field_name="symbol",
            ),
            "side": self._required_text(
                side,
                field_name="side",
            ).upper(),
            "positionSide": self._required_text(
                position_side,
                field_name="position_side",
            ).upper(),
            "type": self._required_text(
                order_type,
                field_name="order_type",
            ).upper(),
            "quantity": quantity,
        }

        optional_params = {
            "price": price,
            "stopPrice": stop_price,
            "stopLoss": stop_loss,
            "takeProfit": take_profit,
            "timeInForce": time_in_force,
            "clientOrderId": client_order_id,
        }
        params.update(
            {
                key: value
                for key, value in optional_params.items()
                if value is not None and value != ""
            }
        )

        response = await self.request(
            "POST",
            "/openApi/swap/v2/trade/order",
            params=params,
            signed=True,
            retry_safe=False,
        )
        return self._parse_order(self._order_mapping(response))

    async def cancel_order(
        self,
        symbol: str,
        order_id: str,
    ) -> dict[str, Any]:
        return await self.request(
            "DELETE",
            "/openApi/swap/v2/trade/order",
            params={
                "symbol": self._required_text(
                    symbol,
                    field_name="symbol",
                ),
                "orderId": self._required_text(
                    order_id,
                    field_name="order_id",
                ),
            },
            signed=True,
            retry_safe=False,
        )

    async def cancel_all_orders(
        self,
        symbol: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {}

        if symbol is not None:
            params["symbol"] = self._required_text(
                symbol,
                field_name="symbol",
            )

        return await self.request(
            "DELETE",
            "/openApi/swap/v2/trade/allOpenOrders",
            params=params,
            signed=True,
            retry_safe=False,
        )

    async def get_order(
        self,
        symbol: str,
        order_id: str,
    ) -> BingXOrder:
        response = await self.request(
            "GET",
            "/openApi/swap/v2/trade/order",
            params={
                "symbol": self._required_text(
                    symbol,
                    field_name="symbol",
                ),
                "orderId": self._required_text(
                    order_id,
                    field_name="order_id",
                ),
            },
            signed=True,
        )
        return self._parse_order(self._order_mapping(response))

    async def get_open_orders(
        self,
        symbol: str | None = None,
    ) -> list[BingXOrder]:
        params: dict[str, Any] = {}

        if symbol is not None:
            params["symbol"] = self._required_text(
                symbol,
                field_name="symbol",
            )

        response = await self.request(
            "GET",
            "/openApi/swap/v2/trade/openOrders",
            params=params,
            signed=True,
        )
        data = response.get("data", [])
        items: Sequence[Any]

        if isinstance(data, Mapping):
            nested = data.get("orders", [])

            if isinstance(nested, Sequence) and not isinstance(
                nested,
                (str, bytes, bytearray),
            ):
                items = nested
            else:
                items = []
        elif isinstance(data, Sequence) and not isinstance(
            data,
            (str, bytes, bytearray),
        ):
            items = data
        else:
            items = []

        return [self._parse_order(item) for item in items if isinstance(item, Mapping)]

    async def set_leverage(
        self,
        symbol: str,
        leverage: int,
        position_side: str = "BOTH",
    ) -> dict[str, Any]:
        return await self.request(
            "POST",
            "/openApi/swap/v2/trade/leverage",
            params={
                "symbol": self._required_text(
                    symbol,
                    field_name="symbol",
                ),
                "leverage": self._validate_integer(
                    leverage,
                    field_name="leverage",
                    minimum=1,
                ),
                "positionSide": self._required_text(
                    position_side,
                    field_name="position_side",
                ).upper(),
            },
            signed=True,
            retry_safe=False,
        )

    async def set_margin_type(
        self,
        symbol: str,
        margin_type: str,
    ) -> dict[str, Any]:
        return await self.request(
            "POST",
            "/openApi/swap/v2/trade/marginType",
            params={
                "symbol": self._required_text(
                    symbol,
                    field_name="symbol",
                ),
                "marginType": self._required_text(
                    margin_type,
                    field_name="margin_type",
                ).upper(),
            },
            signed=True,
            retry_safe=False,
        )

    async def get_position_mode(self) -> str:
        response = await self.request(
            "GET",
            "/openApi/swap/v2/user/positionMode",
            signed=True,
        )
        data = self._mapping_data(response)
        return self._required_text(
            data.get("positionMode", "ONE_WAY"),
            field_name="positionMode",
        )

    async def set_position_mode(
        self,
        mode: str,
    ) -> dict[str, Any]:
        return await self.request(
            "POST",
            "/openApi/swap/v2/user/positionMode",
            params={
                "positionMode": self._required_text(
                    mode,
                    field_name="mode",
                ).upper(),
            },
            signed=True,
            retry_safe=False,
        )

    async def close_all_positions(
        self,
        symbol: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {}

        if symbol is not None:
            params["symbol"] = self._required_text(
                symbol,
                field_name="symbol",
            )

        return await self.request(
            "POST",
            "/openApi/swap/v2/trade/closeAllPositions",
            params=params,
            signed=True,
            retry_safe=False,
        )

    async def _get_client(self) -> httpx.AsyncClient:
        async with self._client_lock:
            if self._closed:
                raise RuntimeError("BingX HTTP client is closed.")

            if self._client is None:
                self._client = httpx.AsyncClient(
                    timeout=httpx.Timeout(self.timeout),
                    limits=httpx.Limits(
                        max_connections=100,
                        max_keepalive_connections=20,
                    ),
                    follow_redirects=False,
                )

            return self._client

    async def _send(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str],
        data: Mapping[str, str] | None,
    ) -> httpx.Response:
        client = await self._get_client()
        return await client.request(
            method,
            url,
            headers=dict(headers),
            json=None if data is None else dict(data),
        )

    def _decode_response(
        self,
        response: httpx.Response,
        *,
        operation: str,
        signed: bool,
    ) -> dict[str, Any]:
        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            raise RateLimitError(
                message="BingX rate limit exceeded.",
                exchange="bingx",
                error_code=response.status_code,
                retry_after=retry_after,
                operation=operation,
            )

        if signed and response.status_code in {401, 403}:
            raise AuthenticationError(
                message="BingX authentication was rejected.",
                exchange="bingx",
                error_code=response.status_code,
                operation=operation,
            )

        if response.status_code >= 500:
            raise ExchangeNotAvailableError(
                message="BingX service is unavailable.",
                exchange="bingx",
                error_code=response.status_code,
                operation=operation,
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise ExchangeError(
                message="BingX returned invalid JSON.",
                exchange="bingx",
                error_code=response.status_code,
                operation=operation,
            ) from exc

        if not isinstance(payload, Mapping):
            raise ExchangeError(
                message="BingX returned a non-object JSON response.",
                exchange="bingx",
                error_code=response.status_code,
                operation=operation,
            )

        if response.status_code >= 400:
            raise ExchangeError(
                message="BingX HTTP request was rejected.",
                exchange="bingx",
                error_code=response.status_code,
                raw_response=payload,
                operation=operation,
            )

        return dict(payload)

    def _raise_for_error_payload(
        self,
        payload: Mapping[str, Any],
        *,
        status_code: int,
        operation: str,
    ) -> None:
        raw_code = payload.get("code", 0)

        try:
            code = int(raw_code)
        except (TypeError, ValueError):
            code = -1

        if code == 0 and payload.get("success", True) is not False:
            return

        message = str(
            payload.get("msg") or payload.get("message") or "BingX request failed."
        ).strip()
        exception_type: type[ExchangeError]

        if code in _AUTHENTICATION_CODES:
            exception_type = AuthenticationError
        elif code in _RATE_LIMIT_CODES:
            exception_type = RateLimitError
        elif code in _INSUFFICIENT_FUNDS_CODES:
            exception_type = InsufficientFundsError
        elif code in _INVALID_SYMBOL_CODES:
            exception_type = InvalidSymbolError
        elif code in _UNAVAILABLE_CODES:
            exception_type = ExchangeNotAvailableError
        elif code in _ORDER_CODES:
            exception_type = OrderError
        else:
            exception_type = ExchangeError

        common = {
            "message": f"BingX error [{code}]: {message}",
            "exchange": "bingx",
            "error_code": code if code >= 0 else status_code,
            "raw_response": payload,
            "operation": operation,
        }

        if exception_type is RateLimitError:
            raise RateLimitError(
                **common,
                retry_after=payload.get("retryAfter"),
            )

        raise exception_type(**common)

    def _retry_delay(
        self,
        attempt_index: int,
        error: ExchangeError,
    ) -> float:
        delay = min(
            self.retry_base_delay * (2**attempt_index),
            self.retry_max_delay,
        )

        if isinstance(error, RateLimitError):
            retry_after = error.retry_after

            if retry_after is not None:
                delay = max(
                    delay,
                    min(retry_after, self.retry_max_delay),
                )

        return delay

    def _generate_signature(self, signing_string: str) -> str:
        secret = self.api_secret or ""
        return hmac.new(
            secret.encode("utf-8"),
            signing_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    @staticmethod
    def _build_signing_string(
        params: Mapping[str, str],
    ) -> str:
        return "&".join(
            f"{key}={value}"
            for key, value in sorted(params.items())
            if key != "signature"
        )

    @staticmethod
    def _build_url(
        base_url: str,
        endpoint: str,
        params: Mapping[str, str],
    ) -> str:
        query = "&".join(
            f"{quote(key, safe='-_.~')}=" f"{quote(value, safe='-_.~')}"
            for key, value in sorted(params.items())
        )

        if not query:
            return f"{base_url}{endpoint}"

        return f"{base_url}{endpoint}?{query}"

    @classmethod
    def _normalize_params(
        cls,
        params: Mapping[str, Any] | None,
    ) -> dict[str, str]:
        if params is None:
            return {}

        if not isinstance(params, Mapping):
            raise TypeError("params and data must be mappings or None.")

        normalized: dict[str, str] = {}

        for key, value in params.items():
            if value is None:
                continue

            normalized_key = cls._required_text(
                str(key),
                field_name="parameter key",
            )
            normalized[normalized_key] = cls._stringify_param(value)

        return normalized

    @classmethod
    def _stringify_param(cls, value: Any) -> str:
        if isinstance(value, Enum):
            return str(value.value)

        if isinstance(value, Decimal):
            return format(value, "f")

        if isinstance(value, bool):
            return "true" if value else "false"

        if isinstance(value, datetime):
            timestamp = value.timestamp() * 1_000
            return str(int(timestamp))

        if isinstance(value, (list, tuple, dict)):
            return json.dumps(
                value,
                separators=(",", ":"),
                ensure_ascii=False,
                default=cls._json_default,
            )

        return str(value)

    @staticmethod
    def _json_default(value: Any) -> Any:
        if isinstance(value, Decimal):
            return format(value, "f")

        if isinstance(value, Enum):
            return value.value

        raise TypeError(f"Unsupported request parameter type: {type(value).__name__}")

    def _timestamp_ms(self) -> int:
        value = self._clock_ms()

        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError("clock_ms must return an integer.")

        if value < 0:
            raise ValueError("clock_ms must return a non-negative integer.")

        return value

    def _require_credentials(self) -> None:
        if not self.api_key or not self.api_secret:
            raise AuthenticationError(
                message=(
                    "BingX API key and secret are required for "
                    "authenticated requests."
                ),
                exchange="bingx",
                operation="sign_request",
            )

    @staticmethod
    def _mapping_data(
        response: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        data = response.get("data", {})

        if not isinstance(data, Mapping):
            raise ExchangeError(
                message="BingX response data must be an object.",
                exchange="bingx",
                operation="parse_response",
            )

        return data

    @staticmethod
    def _sequence_data(
        response: Mapping[str, Any],
    ) -> Sequence[Any]:
        data = response.get("data", [])

        if not isinstance(data, Sequence) or isinstance(data, (str, bytes, bytearray)):
            raise ExchangeError(
                message="BingX response data must be an array.",
                exchange="bingx",
                operation="parse_response",
            )

        return data

    @classmethod
    def _single_mapping_data(
        cls,
        response: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        data = response.get("data", {})

        if isinstance(data, Mapping):
            return data

        if (
            isinstance(data, Sequence)
            and not isinstance(data, (str, bytes, bytearray))
            and data
            and isinstance(data[0], Mapping)
        ):
            return data[0]

        raise ExchangeError(
            message="BingX response does not contain an object.",
            exchange="bingx",
            operation="parse_response",
        )

    @classmethod
    def _order_mapping(
        cls,
        response: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        data = response.get("data", {})

        if isinstance(data, Mapping):
            order = data.get("order", data)

            if isinstance(order, Mapping):
                return order

        raise ExchangeError(
            message="BingX order response is malformed.",
            exchange="bingx",
            operation="parse_order",
        )

    @staticmethod
    def _parse_order(item: Mapping[str, Any]) -> BingXOrder:
        return BingXOrder(
            order_id=item.get(
                "orderID",
                item.get("orderId", ""),
            ),
            symbol=item.get("symbol", ""),
            side=item.get("side", "BUY"),
            position_side=item.get("positionSide", "BOTH"),
            order_type=item.get("type", "MARKET"),
            status=item.get("status", "NEW"),
            price=item.get("price", 0),
            quantity=item.get("origQty", item.get("quantity", 0)),
            executed_qty=item.get("executedQty", 0),
            avg_price=item.get("avgPrice", 0),
            stop_loss=item.get("stopLoss"),
            take_profit=item.get("takeProfit"),
            created_at=item.get(
                "time",
                item.get("createTime"),
            ),
            updated_at=item.get("updateTime"),
        )

    @staticmethod
    def _parse_kline(item: Any) -> BingXKline:
        if isinstance(item, Mapping):
            return BingXKline(
                open_time=item.get(
                    "openTime",
                    item.get("time", 0),
                ),
                open=item.get("open", 0),
                high=item.get("high", 0),
                low=item.get("low", 0),
                close=item.get("close", 0),
                volume=item.get("volume", 0),
                close_time=item.get(
                    "closeTime",
                    item.get("time", 0),
                ),
                quote_volume=item.get(
                    "quoteVolume",
                    item.get("quoteAssetVolume", 0),
                ),
                trades_count=item.get(
                    "tradesCount",
                    item.get("trades", 0),
                ),
                taker_buy_volume=item.get(
                    "takerBuyVolume",
                    item.get("takerBuyBaseAssetVolume", 0),
                ),
                taker_buy_quote_volume=item.get(
                    "takerBuyQuoteVolume",
                    item.get("takerBuyQuoteAssetVolume", 0),
                ),
            )

        if (
            isinstance(item, Sequence)
            and not isinstance(item, (str, bytes, bytearray))
            and len(item) >= 11
        ):
            return BingXKline(
                open_time=item[0],
                open=item[1],
                high=item[2],
                low=item[3],
                close=item[4],
                volume=item[5],
                close_time=item[6],
                quote_volume=item[7],
                trades_count=item[8],
                taker_buy_volume=item[9],
                taker_buy_quote_volume=item[10],
            )

        raise ExchangeError(
            message="BingX kline payload is malformed.",
            exchange="bingx",
            operation="parse_klines",
        )

    @staticmethod
    def _normalize_method(method: str) -> str:
        normalized = BingXHttpClient._required_text(
            method,
            field_name="method",
        ).upper()

        if normalized not in {
            "GET",
            "POST",
            "PUT",
            "DELETE",
            "PATCH",
            "HEAD",
            "OPTIONS",
        }:
            raise ValueError(f"Unsupported HTTP method: {normalized}")

        return normalized

    @staticmethod
    def _normalize_endpoint(endpoint: str) -> str:
        normalized = BingXHttpClient._required_text(
            endpoint,
            field_name="endpoint",
        )

        if not normalized.startswith("/"):
            raise ValueError("endpoint must start with '/'.")

        return normalized

    @staticmethod
    def _validate_base_url(value: str) -> str:
        normalized = BingXHttpClient._required_text(
            value,
            field_name="base_url",
        ).rstrip("/")

        if not normalized.startswith("https://"):
            raise ValueError("base_url must use HTTPS.")

        return normalized

    @staticmethod
    def _optional_secret(
        value: str | None,
        *,
        environment_name: str,
    ) -> str | None:
        candidate = os.getenv(environment_name) if value is None else value

        if candidate is None:
            return None

        if not isinstance(candidate, str):
            raise TypeError(f"{environment_name} must be a string or None.")

        normalized = candidate.strip()
        return normalized or None

    @staticmethod
    def _required_text(
        value: Any,
        *,
        field_name: str,
    ) -> str:
        if not isinstance(value, str):
            raise TypeError(f"{field_name} must be a string.")

        normalized = value.strip()

        if not normalized:
            raise ValueError(f"{field_name} cannot be empty.")

        return normalized

    @staticmethod
    def _validate_integer(
        value: Any,
        *,
        field_name: str,
        minimum: int,
        maximum: int | None = None,
    ) -> int:
        if isinstance(value, bool):
            raise TypeError(f"{field_name} must be an integer.")

        try:
            normalized = int(value)
        except (TypeError, ValueError) as exc:
            raise TypeError(f"{field_name} must be an integer.") from exc

        if normalized < minimum:
            raise ValueError(
                f"{field_name} must be greater than or equal to " f"{minimum}."
            )

        if maximum is not None and normalized > maximum:
            raise ValueError(
                f"{field_name} must be less than or equal to " f"{maximum}."
            )

        return normalized

    @staticmethod
    def _validate_positive_number(
        value: Any,
        *,
        field_name: str,
    ) -> float:
        normalized = BingXHttpClient._validate_non_negative_number(
            value,
            field_name=field_name,
        )

        if normalized == 0:
            raise ValueError(f"{field_name} must be greater than zero.")

        return normalized

    @staticmethod
    def _validate_non_negative_number(
        value: Any,
        *,
        field_name: str,
    ) -> float:
        if isinstance(value, bool) or not isinstance(
            value,
            (int, float),
        ):
            raise TypeError(f"{field_name} must be numeric.")

        normalized = float(value)

        if not math.isfinite(normalized):
            raise ValueError(f"{field_name} must be finite.")

        if normalized < 0:
            raise ValueError(f"{field_name} must be greater than or equal to zero.")

        return normalized


def classify_transport_exception(
    error: BaseException,
    *,
    attempted_host: str,
) -> BingXTransportDiagnostic:
    """Classify a complete exception chain without exposing its text."""

    chain = _exception_chain(error)
    reason_code = "unknown_transport_failure"
    transport_stage = "transport"
    matched: BaseException = chain[0]

    matchers: tuple[tuple[str, str, Callable[[BaseException], bool]], ...] = (
        (
            "read_timeout",
            "response_read",
            lambda item: isinstance(item, httpx.ReadTimeout),
        ),
        (
            "connect_timeout",
            "connect",
            lambda item: isinstance(item, httpx.ConnectTimeout)
            or isinstance(item, TimeoutError)
            or _exception_errno(item) in _CONNECT_TIMEOUT_ERRNOS,
        ),
        (
            "proxy_connection_failure",
            "proxy_connect",
            lambda item: isinstance(item, httpx.ProxyError),
        ),
        (
            "certificate_verification_failure",
            "tls_handshake",
            lambda item: isinstance(item, ssl.SSLCertVerificationError),
        ),
        (
            "tls_handshake_failure",
            "tls_handshake",
            lambda item: isinstance(item, ssl.SSLError),
        ),
        (
            "dns_failure",
            "dns_resolution",
            lambda item: isinstance(item, socket.gaierror)
            or _exception_errno(item) in _DNS_ERRNOS,
        ),
        (
            "connection_refused",
            "connect",
            lambda item: isinstance(item, ConnectionRefusedError)
            or _exception_errno(item) in _CONNECTION_REFUSED_ERRNOS,
        ),
        (
            "connection_reset",
            "transport",
            lambda item: isinstance(item, ConnectionResetError)
            or _exception_errno(item) in _CONNECTION_RESET_ERRNOS,
        ),
    )
    for candidate_reason, candidate_stage, matcher in matchers:
        match = next((item for item in chain if matcher(item)), None)
        if match is not None:
            reason_code = candidate_reason
            transport_stage = candidate_stage
            matched = match
            break
    else:
        exchange_error = next(
            (item for item in chain if isinstance(item, ExchangeError)),
            None,
        )
        if exchange_error is not None and exchange_error.error_code is not None:
            reason_code = "http_status_failure"
            transport_stage = "response_status"
            matched = exchange_error

    return BingXTransportDiagnostic(
        attempted_host=_sanitized_host(attempted_host),
        transport_stage=transport_stage,
        exception_type=type(matched).__name__,
        sanitized_errno=_exception_errno(matched),
        reason_code=reason_code,
    )


def _exception_chain(error: BaseException) -> tuple[BaseException, ...]:
    chain: list[BaseException] = []
    current: BaseException | None = error
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        chain.append(current)
        current = current.__cause__ or current.__context__
    return tuple(chain)


def _exception_errno(error: BaseException) -> int | None:
    for name in ("winerror", "errno"):
        value = getattr(error, name, None)
        if isinstance(value, int) and not isinstance(value, bool):
            return value
    return None


def _sanitized_host(value: str) -> str:
    try:
        parsed = urlsplit(value)
        if parsed.scheme != "https" or parsed.hostname is None:
            return "unknown"
        port = "" if parsed.port is None else f":{parsed.port}"
        return f"https://{parsed.hostname}{port}"
    except (TypeError, ValueError):
        return "unknown"


__all__ = (
    "AsyncSleeper",
    "BingXTransportDiagnostic",
    "BingXTransportError",
    "BingXHttpClient",
    "ClockMilliseconds",
    "classify_transport_exception",
)
