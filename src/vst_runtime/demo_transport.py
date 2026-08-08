"""Narrow async deployment adapter for the manual BingX VST Demo canary."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
from typing import Any, NoReturn

from src.exchange.bingx_client import BingXHttpClient, BingXTransportError
from src.exchange.exceptions import (
    AuthenticationError,
    ExchangeError,
    NetworkError,
    OrderError,
)
from src.exchange.models import BingXBalance, BingXPosition
from src.execution_intent.models import decimal_text

from .demo_order import (
    DEFAULT_DEMO_CANARY_POLICY,
    AsyncDemoOrderTransport,
    DemoAmbiguousSubmission,
    DemoCanaryError,
    DemoContractConstraints,
    DemoLeverageSnapshot,
    DemoOrderPlan,
    DemoTopOfBook,
)
from .models import (
    VST_BASE_URLS,
    RemoteOrder,
    RemoteOrderStatus,
    VstConfiguration,
)


class BingXAsyncDemoOrderAdapter:
    """Composition wrapper exposing only reads and the single canary lifecycle."""

    __slots__ = ("__client",)

    def __init__(self, client: BingXHttpClient) -> None:
        if not isinstance(client, BingXHttpClient):
            raise TypeError("client must be a BingXHttpClient")
        self.__client = client

    @property
    def selected_host(self) -> str:
        return self.__client.last_attempted_base_url

    async def fetch_constraints(self, symbol: str) -> DemoContractConstraints:
        normalized = _symbol(symbol)
        failure: DemoCanaryError
        try:
            contracts = await self.__client.get_symbols()
            item = next(
                value
                for value in contracts
                if str(value.get("symbol", "")).upper() == normalized
            )
            price_precision = _integer(item.get("pricePrecision"), "constraints")
            quantity_precision = _integer(
                item.get("quantityPrecision"), "constraints"
            )
            return DemoContractConstraints(
                symbol=normalized,
                price_tick=Decimal(1).scaleb(-price_precision),
                quantity_step=Decimal(1).scaleb(-quantity_precision),
                minimum_quantity=_positive_decimal(
                    item.get("tradeMinQuantity"), "constraints"
                ),
                minimum_notional=_positive_decimal(
                    item.get("tradeMinUSDT"), "constraints"
                ),
                maximum_long_leverage=(
                    DEFAULT_DEMO_CANARY_POLICY.maximum_leverage
                ),
                maximum_short_leverage=(
                    DEFAULT_DEMO_CANARY_POLICY.maximum_leverage
                ),
                trading_enabled=_trading_enabled(item),
            )
        except StopIteration:
            failure = DemoCanaryError("unsupported_symbol")
        except DemoCanaryError as error:
            failure = error
        except Exception as error:
            failure = _read_failure(error, "invalid_constraints_schema")
        _raise_failure(failure)

    async def fetch_orderbook(self, symbol: str) -> DemoTopOfBook:
        normalized = _symbol(symbol)
        failure: DemoCanaryError
        try:
            book = await self.__client.get_orderbook(normalized, limit=5)
            return DemoTopOfBook(
                symbol=normalized,
                best_bid=book.best_bid,
                best_ask=book.best_ask,
                update_id=str(book.last_update_id),
            )
        except Exception as error:
            failure = _read_failure(error, "invalid_orderbook_schema")
        _raise_failure(failure)

    async def fetch_balances(self) -> Sequence[BingXBalance]:
        failure: DemoCanaryError
        try:
            return tuple(await self.__client.get_balance())
        except Exception as error:
            failure = _read_failure(error, "balance_read_failed")
        _raise_failure(failure)

    async def fetch_positions(self, symbol: str) -> Sequence[BingXPosition]:
        failure: DemoCanaryError
        try:
            return tuple(await self.__client.get_positions(_symbol(symbol)))
        except Exception as error:
            failure = _read_failure(error, "positions_read_failed")
        _raise_failure(failure)

    async def fetch_leverage(self, symbol: str) -> DemoLeverageSnapshot:
        normalized = _symbol(symbol)
        failure: DemoCanaryError
        try:
            response = await self.__client.request(
                "GET",
                "/openApi/swap/v2/trade/leverage",
                params={"symbol": normalized},
                signed=True,
            )
            item = _single_mapping(response)
            return DemoLeverageSnapshot(
                symbol=normalized,
                long_leverage=_integer(item.get("longLeverage"), "leverage"),
                short_leverage=_integer(item.get("shortLeverage"), "leverage"),
            )
        except Exception as error:
            failure = _read_failure(error, "invalid_leverage_schema")
        _raise_failure(failure)

    async def fetch_position_mode(self) -> str:
        failure: DemoCanaryError
        try:
            response = await self.__client.request(
                "GET",
                "/openApi/swap/v1/positionSide/dual",
                signed=True,
            )
            item = _single_mapping(response)
            return "HEDGE" if _boolean(item.get("dualSidePosition")) else "ONE_WAY"
        except Exception as error:
            failure = _read_failure(error, "invalid_position_mode_schema")
        _raise_failure(failure)

    async def fetch_open_orders(self, symbol: str) -> Sequence[RemoteOrder]:
        normalized = _symbol(symbol)
        failure: DemoCanaryError
        try:
            response = await self.__client.request(
                "GET",
                "/openApi/swap/v2/trade/openOrders",
                params={"symbol": normalized},
                signed=True,
            )
            return tuple(
                _parse_remote_order(item)
                for item in _sequence_mappings(response)
            )
        except Exception as error:
            failure = _read_failure(error, "invalid_open_orders_schema")
        _raise_failure(failure)

    async def fetch_recent_orders(self, symbol: str) -> Sequence[RemoteOrder]:
        normalized = _symbol(symbol)
        failure: DemoCanaryError
        try:
            response = await self.__client.request(
                "GET",
                "/openApi/swap/v2/trade/allOrders",
                params={"symbol": normalized, "limit": 1_000},
                signed=True,
            )
            return tuple(
                _parse_remote_order(item)
                for item in _sequence_mappings(response)
            )
        except Exception as error:
            failure = _read_failure(error, "invalid_recent_orders_schema")
        _raise_failure(failure)

    async def submit_protected_limit(self, plan: DemoOrderPlan) -> RemoteOrder:
        params: dict[str, Any] = {
            "clientOrderId": plan.client_order_id,
            "positionSide": plan.position_side,
            "price": plan.limit_price,
            "quantity": plan.quantity,
            "side": plan.side,
            "stopLoss": _protection_json("STOP_MARKET", plan.stop_loss),
            "symbol": plan.symbol,
            "takeProfit": _protection_json(
                "TAKE_PROFIT_MARKET", plan.take_profit
            ),
            "timeInForce": plan.time_in_force,
            "type": "LIMIT",
        }
        failure: DemoCanaryError
        try:
            response = await self.__client.request(
                "POST",
                "/openApi/swap/v2/trade/order",
                params=params,
                signed=True,
                retry_safe=False,
            )
            return _parse_remote_order(
                _single_mapping(response),
                fallback_client_order_id=plan.client_order_id,
            )
        except (BingXTransportError, NetworkError, TimeoutError, OSError):
            failure = DemoAmbiguousSubmission()
        except AuthenticationError:
            failure = DemoCanaryError("authentication_rejected")
        except OrderError as error:
            if error.error_code == "101481":
                failure = DemoAmbiguousSubmission()
            else:
                failure = DemoCanaryError(
                    _order_rejection_reason(error)
                )
        except ExchangeError:
            failure = DemoAmbiguousSubmission()
        except Exception:
            # Once dispatch may have occurred, even a successful response with
            # an unusable schema has an unknown remote outcome. Recovery must
            # query the deterministic client ID and must never resubmit.
            failure = DemoAmbiguousSubmission()
        _raise_failure(failure)

    async def query_order(
        self,
        symbol: str,
        client_order_id: str,
    ) -> RemoteOrder | None:
        normalized_id = _client_order_id(client_order_id)
        failure: DemoCanaryError
        try:
            response = await self.__client.request(
                "GET",
                "/openApi/swap/v2/trade/order",
                params={
                    "clientOrderId": normalized_id,
                    "symbol": _symbol(symbol),
                },
                signed=True,
            )
            return _parse_remote_order(
                _single_mapping(response),
                fallback_client_order_id=normalized_id,
            )
        except OrderError as error:
            if error.error_code == "109421":
                return None
            failure = _read_failure(error, "order_query_failed")
        except Exception as error:
            failure = _read_failure(error, "order_query_failed")
        _raise_failure(failure)

    async def cancel_order(
        self,
        symbol: str,
        client_order_id: str,
    ) -> RemoteOrder | None:
        normalized_id = _client_order_id(client_order_id)
        failure: DemoCanaryError
        try:
            response = await self.__client.request(
                "DELETE",
                "/openApi/swap/v2/trade/order",
                params={
                    "clientOrderId": normalized_id,
                    "symbol": _symbol(symbol),
                },
                signed=True,
                retry_safe=False,
            )
            return _parse_remote_order(
                _single_mapping(response),
                fallback_client_order_id=normalized_id,
            )
        except Exception:
            failure = DemoCanaryError("cancel_outcome_ambiguous")
        _raise_failure(failure)

    async def close(self) -> None:
        failure: DemoCanaryError
        try:
            await self.__client.close()
            return
        except Exception:
            failure = DemoCanaryError("transport_close_failed")
        _raise_failure(failure)


def create_async_demo_order_transport(
    configuration: VstConfiguration,
    *,
    selected_host: str,
) -> AsyncDemoOrderTransport:
    """Create the existing HTTP client pinned to readiness's actual VST host."""

    normalized_host = selected_host.rstrip("/")
    if normalized_host not in VST_BASE_URLS:
        raise DemoCanaryError("selected_host_not_vst")
    if configuration.base_url not in VST_BASE_URLS:
        raise DemoCanaryError("selected_host_not_vst")
    client = BingXHttpClient(
        api_key=configuration.api_key,
        api_secret=configuration.api_secret,
        demo_mode=True,
        base_url=normalized_host,
        recv_window=configuration.recv_window_ms,
        timeout=configuration.timeout_seconds,
    )
    return BingXAsyncDemoOrderAdapter(client)


def _parse_remote_order(
    item: Mapping[str, Any],
    *,
    fallback_client_order_id: str | None = None,
) -> RemoteOrder:
    order_id = str(item.get("orderID") or item.get("orderId") or "").strip()
    if not order_id:
        raise DemoCanaryError("invalid_order_response_schema")
    client_id = str(item.get("clientOrderId") or fallback_client_order_id or "").strip()
    if not client_id:
        client_id = f"exchange{order_id}"
    raw_status = str(item.get("status", "UNKNOWN")).upper()
    if raw_status == "CANCELLED":
        raw_status = "CANCELED"
    try:
        status = RemoteOrderStatus(raw_status)
    except ValueError:
        status = RemoteOrderStatus.UNKNOWN
    original = _non_negative_decimal(
        item.get("origQty", item.get("quantity", 0)), "order"
    )
    filled = _non_negative_decimal(
        item.get("executedQty", item.get("cumQty", 0)), "order"
    )
    return RemoteOrder(
        client_order_id=client_id,
        order_id=order_id,
        symbol=str(item.get("symbol", "")),
        side=str(item.get("side", "")),
        order_type=str(item.get("type", "")),
        status=status,
        original_quantity=original,
        filled_quantity=filled,
        average_price=_non_negative_decimal(item.get("avgPrice", 0), "order"),
        price=_non_negative_decimal(item.get("price", 0), "order"),
        update_id=str(item.get("updateTime") or item.get("time") or order_id),
        updated_at_ms=_integer(
            item.get("updateTime", item.get("time", 0)),
            "order",
            minimum=0,
        ),
        reduce_only=_boolean(item.get("reduceOnly", False)),
    )


def _single_mapping(response: Mapping[str, Any]) -> Mapping[str, Any]:
    data = response.get("data")
    if not isinstance(data, Mapping):
        raise DemoCanaryError("invalid_response_schema")
    nested = data.get("order")
    return nested if isinstance(nested, Mapping) else data


def _sequence_mappings(response: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    if "data" not in response:
        raise DemoCanaryError("invalid_response_schema")
    data = response["data"]
    if isinstance(data, Mapping):
        if "orders" not in data:
            raise DemoCanaryError("invalid_response_schema")
        data = data["orders"]
    if not isinstance(data, Sequence) or isinstance(data, (str, bytes, bytearray)):
        raise DemoCanaryError("invalid_response_schema")
    if any(not isinstance(item, Mapping) for item in data):
        raise DemoCanaryError("invalid_response_schema")
    return tuple(item for item in data if isinstance(item, Mapping))


def _raise_failure(error: DemoCanaryError) -> NoReturn:
    """Raise a safe error without retaining the sensitive source exception."""

    error.__cause__ = None
    error.__context__ = None
    error.__traceback__ = None
    raise error


def _trading_enabled(item: Mapping[str, Any]) -> bool:
    status = item.get("status")
    state = item.get("apiStateOpen")
    status_ok = status in (1, "1", True, "true", "TRUE")
    state_ok = state in (1, "1", True, "true", "TRUE")
    return status_ok and state_ok


def _protection_json(order_type: str, stop_price: Decimal) -> str:
    price = decimal_text(stop_price)
    return (
        '{"stopGuaranteed":false,"stopPrice":'
        f"{price},\"type\":\"{order_type}\","
        '"workingType":"MARK_PRICE"}'
    )


def _order_rejection_reason(error: OrderError) -> str:
    code = str(error.error_code or "").strip()

    if code.isdigit():
        return f"order_rejected_{code}"

    return "order_rejected"


def _read_failure(error: BaseException, schema_reason: str) -> DemoCanaryError:
    if isinstance(error, DemoCanaryError):
        return error
    if isinstance(error, AuthenticationError):
        return DemoCanaryError("authentication_rejected")
    if isinstance(error, BingXTransportError):
        return DemoCanaryError(error.reason_code)
    if isinstance(error, NetworkError):
        return DemoCanaryError("network_failure")
    if isinstance(error, ExchangeError):
        return DemoCanaryError("exchange_read_rejected")
    return DemoCanaryError(schema_reason)


def _positive_decimal(value: object, field: str) -> Decimal:
    result = _non_negative_decimal(value, field)
    if result <= 0:
        raise DemoCanaryError(f"invalid_{field}_schema")
    return result


def _non_negative_decimal(value: object, field: str) -> Decimal:
    if isinstance(value, bool):
        raise DemoCanaryError(f"invalid_{field}_schema")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise DemoCanaryError(f"invalid_{field}_schema") from None
    if not result.is_finite() or result < 0:
        raise DemoCanaryError(f"invalid_{field}_schema")
    return result.normalize()


def _integer(value: object, field: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool):
        raise DemoCanaryError(f"invalid_{field}_schema")
    try:
        result = int(str(value))
    except (TypeError, ValueError):
        raise DemoCanaryError(f"invalid_{field}_schema") from None
    if result < minimum:
        raise DemoCanaryError(f"invalid_{field}_schema")
    return result


def _boolean(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        if value.casefold() == "true":
            return True
        if value.casefold() == "false":
            return False
    if value in (0, 1):
        return bool(value)
    raise DemoCanaryError("invalid_order_response_schema")


def _symbol(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DemoCanaryError("unsupported_symbol")
    return value.strip().upper()


def _client_order_id(value: str) -> str:
    if (
        not isinstance(value, str)
        or not value.isalnum()
        or not 1 <= len(value) <= 40
    ):
        raise DemoCanaryError("invalid_client_order_id")
    return value.casefold()


__all__ = (
    "BingXAsyncDemoOrderAdapter",
    "create_async_demo_order_transport",
)
