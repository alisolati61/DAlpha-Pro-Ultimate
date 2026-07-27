"""Asynchronous BingX adapter for the stable exchange contract."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping
from decimal import Decimal, InvalidOperation
from typing import Any, TypeAlias

from src.exchange.base import BaseExchange
from src.exchange.bingx_client import BingXHttpClient
from src.exchange.exceptions import ExchangeError, OrderError
from src.exchange.models import (
    BingXBalance,
    BingXFundingRate,
    BingXKline,
    BingXOrder,
    BingXOrderBook,
    BingXOrderSide,
    BingXOrderType,
    BingXPosition,
    BingXPositionSide,
    BingXTicker,
    BingXTimeInForce,
    BingXTrade,
)

ClientFactory: TypeAlias = Callable[..., BingXHttpClient]


class BingXAdapter(BaseExchange):
    """Translate BingX transport models into exchange-neutral values.

    The adapter is fully asynchronous and owns the lifecycle of its HTTP
    client. Factory-created clients can be recreated after ``disconnect``;
    injected clients are treated as externally constructed one-shot clients.
    """

    exchange_name = "bingx"

    def __init__(
        self,
        api_key: str | None = None,
        api_secret: str | None = None,
        demo_mode: bool | None = None,
        *,
        client: BingXHttpClient | None = None,
        client_factory: ClientFactory = BingXHttpClient,
        health_timeout: float = 10.0,
        default_position_side: str = "BOTH",
        **client_config: Any,
    ) -> None:
        self._health_timeout = self._positive_float(
            health_timeout,
            field_name="health_timeout",
        )
        self._default_position_side = self._position_side(
            default_position_side
        )
        self._lifecycle_lock = asyncio.Lock()
        self._connected = False
        self._client_closed = False
        self._order_symbols: dict[str, str] = {}

        if client is not None:
            if (
                api_key is not None
                or api_secret is not None
                or demo_mode is not None
                or client_config
            ):
                raise ValueError(
                    "Client configuration cannot be supplied when "
                    "a BingX client is injected."
                )

            self._validate_client(client)
            self._client = client
            self._client_factory: ClientFactory | None = None
            self._client_config: dict[str, Any] = {}
            return

        if not callable(client_factory):
            raise TypeError("client_factory must be callable.")

        self._client_factory = client_factory
        self._client_config = {
            "api_key": api_key,
            "api_secret": api_secret,
            "demo_mode": demo_mode,
            **client_config,
        }
        self._client = self._create_client()

    @property
    def is_connected(self) -> bool:
        """Return the adapter's local lifecycle state."""

        return self._connected

    @property
    def client(self) -> BingXHttpClient:
        """Return the active low-level client."""

        return self._client

    async def connect(self) -> None:
        """Verify BingX availability and enter the connected state once."""

        async with self._lifecycle_lock:
            if self._connected:
                return

            if self._client_closed:
                if self._client_factory is None:
                    raise ExchangeError(
                        message=(
                            "Injected BingX client cannot be reused after "
                            "disconnect."
                        ),
                        exchange="bingx",
                        operation="connect",
                    )

                self._client = self._create_client()
                self._client_closed = False

            try:
                async with asyncio.timeout(self._health_timeout):
                    await self._client.get_server_time()
            except asyncio.CancelledError:
                raise
            except ExchangeError:
                raise
            except Exception as exc:
                raise ExchangeError(
                    message="Failed to connect to BingX.",
                    exchange="bingx",
                    operation="connect",
                ) from exc

            self._connected = True

    async def disconnect(self) -> None:
        """Close the active HTTP client exactly once."""

        async with self._lifecycle_lock:
            if self._client_closed:
                self._connected = False
                return

            try:
                await self._client.close()
            finally:
                self._connected = False
                self._client_closed = True

    async def health_check(self) -> bool:
        """Return whether the connected BingX endpoint responds."""

        if not self._connected or self._client_closed:
            return False

        try:
            async with asyncio.timeout(self._health_timeout):
                await self._client.get_server_time()
        except asyncio.CancelledError:
            raise
        except Exception:
            return False

        return True

    async def verify_connection(self) -> dict[str, Any]:
        """Return a structured connectivity report."""

        await self.connect()
        server_time = await self._client.get_server_time()

        return {
            "status": "connected",
            "exchange": self.exchange_name,
            "server_time": server_time,
            "demo_mode": bool(
                getattr(self._client, "demo_mode", False)
            ),
        }

    async def fetch_balance(
        self,
    ) -> dict[str, dict[str, Decimal]]:
        """Return balances in a CCXT-compatible mapping shape."""

        balances = await self._client.get_balance()
        result: dict[str, dict[str, Decimal]] = {}

        for balance in balances:
            used = max(
                balance.margin_balance - balance.available_balance,
                Decimal("0"),
            )
            result[balance.asset] = {
                "free": balance.available_balance,
                "used": used,
                "total": balance.margin_balance,
                "wallet_balance": balance.wallet_balance,
                "unrealized_pnl": balance.unrealized_pnl,
                "max_withdraw_amount": (
                    balance.max_withdraw_amount
                ),
            }

        return result

    async def fetch_positions(
        self,
    ) -> list[dict[str, Any]]:
        """Return open positions in an exchange-neutral mapping shape."""

        positions = await self._client.get_positions()
        return [
            self._position_to_dict(position)
            for position in positions
        ]

    async def fetch_ticker(
        self,
        symbol: str,
    ) -> dict[str, Any]:
        """Return one ticker in a CCXT-compatible mapping shape."""

        ticker = await self._client.get_ticker(
            self._required_text(symbol, field_name="symbol")
        )
        return self._ticker_to_dict(ticker)

    async def fetch_orderbook(
        self,
        symbol: str,
    ) -> dict[str, Any]:
        """Return one normalized order book."""

        book = await self._client.get_orderbook(
            self._required_text(symbol, field_name="symbol")
        )
        return self._orderbook_to_dict(book)

    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 500,
    ) -> list[list[Any]]:
        """Return CCXT-style OHLCV rows."""

        normalized_symbol = self._required_text(
            symbol,
            field_name="symbol",
        )
        normalized_timeframe = self._required_text(
            timeframe,
            field_name="timeframe",
        )
        normalized_limit = self._positive_integer(
            limit,
            field_name="limit",
        )

        klines = await self._client.get_klines(
            symbol=normalized_symbol,
            interval=normalized_timeframe,
            limit=normalized_limit,
        )

        return [
            self._kline_to_row(kline)
            for kline in klines
        ]

    async def create_order(
        self,
        symbol: str,
        order_type: str,
        side: str,
        amount: Decimal | int | float | str,
        price: Decimal | int | float | str | None = None,
        params: Mapping[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Create a BingX order and return an exchange-neutral order mapping."""

        normalized_symbol = self._required_text(
            symbol,
            field_name="symbol",
        )
        normalized_type = self._order_type(order_type)
        normalized_side = self._order_side(side)
        normalized_amount = self._positive_decimal(
            amount,
            field_name="amount",
        )
        normalized_price = self._optional_positive_decimal(
            price,
            field_name="price",
        )

        if (
            normalized_type is BingXOrderType.LIMIT
            and normalized_price is None
        ):
            raise ValueError("price is required for LIMIT orders.")

        options = self._merge_order_options(params, kwargs)
        position_side = self._position_side(
            self._pop_alias(
                options,
                "position_side",
                "positionSide",
                default=self._default_position_side.value,
            )
        )
        time_in_force = self._time_in_force(
            self._pop_alias(
                options,
                "time_in_force",
                "timeInForce",
                default=BingXTimeInForce.GTC.value,
            )
        )
        stop_price = self._optional_positive_decimal(
            self._pop_alias(
                options,
                "stop_price",
                "stopPrice",
                default=None,
            ),
            field_name="stop_price",
        )
        stop_loss = self._optional_positive_decimal(
            self._pop_alias(
                options,
                "stop_loss",
                "stopLoss",
                default=None,
            ),
            field_name="stop_loss",
        )
        take_profit = self._optional_positive_decimal(
            self._pop_alias(
                options,
                "take_profit",
                "takeProfit",
                default=None,
            ),
            field_name="take_profit",
        )
        client_order_id = self._pop_alias(
            options,
            "client_order_id",
            "clientOrderId",
            default=None,
        )

        if client_order_id is not None:
            client_order_id = self._required_text(
                client_order_id,
                field_name="client_order_id",
            )

        if options:
            unsupported = ", ".join(sorted(options))
            raise ValueError(
                f"Unsupported BingX order parameters: {unsupported}"
            )

        order = await self._client.place_order(
            symbol=normalized_symbol,
            side=normalized_side.value,
            position_side=position_side.value,
            order_type=normalized_type.value,
            quantity=normalized_amount,
            price=normalized_price,
            stop_price=stop_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            time_in_force=time_in_force.value,
            client_order_id=client_order_id,
        )
        self._order_symbols[order.order_id] = order.symbol
        return self._order_to_dict(order)

    async def cancel_order(
        self,
        order_id: str,
        symbol: str | None = None,
    ) -> dict[str, Any]:
        """Cancel an order after safely resolving its required symbol."""

        normalized_order_id = self._required_text(
            order_id,
            field_name="order_id",
        )
        resolved_symbol = await self._resolve_order_symbol(
            normalized_order_id,
            symbol,
        )
        response = await self._client.cancel_order(
            resolved_symbol,
            normalized_order_id,
        )
        self._order_symbols.pop(normalized_order_id, None)

        return {
            "id": normalized_order_id,
            "symbol": resolved_symbol,
            "status": "canceled",
            "info": response,
        }

    async def fetch_order(
        self,
        order_id: str,
        symbol: str | None = None,
    ) -> dict[str, Any]:
        """Fetch one order after safely resolving its required symbol."""

        normalized_order_id = self._required_text(
            order_id,
            field_name="order_id",
        )
        resolved_symbol = await self._resolve_order_symbol(
            normalized_order_id,
            symbol,
        )
        order = await self._client.get_order(
            resolved_symbol,
            normalized_order_id,
        )
        self._order_symbols[order.order_id] = order.symbol
        return self._order_to_dict(order)

    async def fetch_open_orders(
        self,
        symbol: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return normalized open orders."""

        normalized_symbol = (
            None
            if symbol is None
            else self._required_text(symbol, field_name="symbol")
        )
        orders = await self._client.get_open_orders(
            normalized_symbol
        )

        for order in orders:
            self._order_symbols[order.order_id] = order.symbol

        return [
            self._order_to_dict(order)
            for order in orders
        ]

    async def get_funding_rate(
        self,
        symbol: str,
    ) -> dict[str, Any]:
        funding = await self._client.get_funding_rate(
            self._required_text(symbol, field_name="symbol")
        )
        return self._funding_to_dict(funding)

    async def get_recent_trades(
        self,
        symbol: str,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        trades = await self._client.get_recent_trades(
            self._required_text(symbol, field_name="symbol"),
            self._positive_integer(limit, field_name="limit"),
        )
        return [
            self._trade_to_dict(trade)
            for trade in trades
        ]

    async def set_leverage(
        self,
        symbol: str,
        leverage: int,
        position_side: str = "BOTH",
    ) -> dict[str, Any]:
        return await self._client.set_leverage(
            self._required_text(symbol, field_name="symbol"),
            self._positive_integer(
                leverage,
                field_name="leverage",
            ),
            self._position_side(position_side).value,
        )

    async def set_margin_type(
        self,
        symbol: str,
        margin_type: str,
    ) -> dict[str, Any]:
        return await self._client.set_margin_type(
            self._required_text(symbol, field_name="symbol"),
            self._required_text(
                margin_type,
                field_name="margin_type",
            ).upper(),
        )

    async def close_all_positions(
        self,
        symbol: str | None = None,
    ) -> dict[str, Any]:
        normalized_symbol = (
            None
            if symbol is None
            else self._required_text(symbol, field_name="symbol")
        )
        return await self._client.close_all_positions(
            normalized_symbol
        )

    # Compatibility aliases used by older integration points.
    async def get_balance(self) -> dict[str, dict[str, Decimal]]:
        return await self.fetch_balance()

    async def get_positions(self) -> list[dict[str, Any]]:
        return await self.fetch_positions()

    async def get_ticker(self, symbol: str) -> dict[str, Any]:
        return await self.fetch_ticker(symbol)

    async def get_orderbook(self, symbol: str) -> dict[str, Any]:
        return await self.fetch_orderbook(symbol)

    async def get_ohlcv(
        self,
        symbol: str,
        timeframe: str = "1h",
        limit: int = 500,
    ) -> list[list[Any]]:
        return await self.fetch_ohlcv(
            symbol,
            timeframe,
            limit,
        )

    async def get_order_status(
        self,
        order_id: str,
        symbol: str | None = None,
    ) -> dict[str, Any]:
        return await self.fetch_order(order_id, symbol)

    async def _resolve_order_symbol(
        self,
        order_id: str,
        symbol: str | None,
    ) -> str:
        if symbol is not None:
            normalized_symbol = self._required_text(
                symbol,
                field_name="symbol",
            )
            self._order_symbols[order_id] = normalized_symbol
            return normalized_symbol

        cached = self._order_symbols.get(order_id)

        if cached is not None:
            return cached

        open_orders = await self._client.get_open_orders()

        for order in open_orders:
            self._order_symbols[order.order_id] = order.symbol

            if order.order_id == order_id:
                return order.symbol

        raise OrderError(
            message=(
                "BingX requires symbol to identify this order. "
                "Provide symbol explicitly when the order is not open "
                "or was not created by this adapter instance."
            ),
            exchange="bingx",
            operation="resolve_order_symbol",
        )

    def _create_client(self) -> BingXHttpClient:
        assert self._client_factory is not None
        client = self._client_factory(**self._client_config)
        self._validate_client(client)
        return client

    @staticmethod
    def _validate_client(client: Any) -> None:
        required_methods = (
            "cancel_order",
            "close",
            "close_all_positions",
            "get_balance",
            "get_funding_rate",
            "get_klines",
            "get_open_orders",
            "get_order",
            "get_orderbook",
            "get_positions",
            "get_recent_trades",
            "get_server_time",
            "get_ticker",
            "place_order",
            "set_leverage",
            "set_margin_type",
        )
        missing = [
            method_name
            for method_name in required_methods
            if not callable(getattr(client, method_name, None))
        ]

        if missing:
            raise TypeError(
                "BingX client is missing required methods: "
                + ", ".join(missing)
            )

    @staticmethod
    def _balance_to_unused_dict(
        balance: BingXBalance,
    ) -> dict[str, Decimal]:
        """Reserved converter for future balance-list APIs."""

        return {
            "wallet_balance": balance.wallet_balance,
            "margin_balance": balance.margin_balance,
        }

    @staticmethod
    def _position_to_dict(
        position: BingXPosition,
    ) -> dict[str, Any]:
        signed_contracts = position.position_amount
        side = position.position_side.value.casefold()

        if position.position_side is BingXPositionSide.BOTH:
            side = "short" if signed_contracts < 0 else "long"

        return {
            "symbol": position.symbol,
            "side": side,
            "contracts": abs(signed_contracts),
            "signed_contracts": signed_contracts,
            "entry_price": position.entry_price,
            "mark_price": position.mark_price,
            "unrealized_pnl": position.unrealized_pnl,
            "liquidation_price": position.liquidation_price,
            "leverage": position.leverage,
            "margin_mode": position.margin_type.casefold(),
            "isolated_margin": position.isolated_margin,
            "percentage": position.pnl_percent,
        }

    @staticmethod
    def _ticker_to_dict(ticker: BingXTicker) -> dict[str, Any]:
        timestamp = (
            None
            if ticker.close_time is None
            else int(ticker.close_time.timestamp() * 1_000)
        )
        return {
            "symbol": ticker.symbol,
            "timestamp": timestamp,
            "datetime": (
                None
                if ticker.close_time is None
                else ticker.close_time.isoformat()
            ),
            "last": ticker.last_price,
            "bid": ticker.bid_price,
            "ask": ticker.ask_price,
            "high": ticker.high_price,
            "low": ticker.low_price,
            "change": ticker.price_change,
            "percentage": ticker.price_change_percent,
            "base_volume": ticker.volume,
            "quote_volume": ticker.quote_volume,
        }

    @staticmethod
    def _orderbook_to_dict(
        book: BingXOrderBook,
    ) -> dict[str, Any]:
        return {
            "symbol": book.symbol,
            "nonce": book.last_update_id,
            "timestamp": None,
            "bids": [
                [price, quantity]
                for price, quantity in book.bids
            ],
            "asks": [
                [price, quantity]
                for price, quantity in book.asks
            ],
            "best_bid": book.best_bid,
            "best_ask": book.best_ask,
            "spread": book.spread,
            "mid_price": book.mid_price,
        }

    @staticmethod
    def _kline_to_row(kline: BingXKline) -> list[Any]:
        return [
            int(kline.open_time.timestamp() * 1_000),
            kline.open,
            kline.high,
            kline.low,
            kline.close,
            kline.volume,
        ]

    @staticmethod
    def _order_to_dict(order: BingXOrder) -> dict[str, Any]:
        remaining = max(
            order.quantity - order.executed_qty,
            Decimal("0"),
        )
        timestamp = (
            None
            if order.created_at is None
            else int(order.created_at.timestamp() * 1_000)
        )
        return {
            "id": order.order_id,
            "symbol": order.symbol,
            "type": order.order_type.value.casefold(),
            "side": order.side.value.casefold(),
            "position_side": (
                order.position_side.value.casefold()
            ),
            "status": order.status.value.casefold(),
            "price": order.price,
            "amount": order.quantity,
            "filled": order.executed_qty,
            "remaining": remaining,
            "average": order.avg_price,
            "stop_loss": order.stop_loss,
            "take_profit": order.take_profit,
            "timestamp": timestamp,
            "datetime": (
                None
                if order.created_at is None
                else order.created_at.isoformat()
            ),
            "last_update_timestamp": (
                None
                if order.updated_at is None
                else int(order.updated_at.timestamp() * 1_000)
            ),
        }

    @staticmethod
    def _funding_to_dict(
        funding: BingXFundingRate,
    ) -> dict[str, Any]:
        return {
            "symbol": funding.symbol,
            "funding_rate": funding.funding_rate,
            "funding_timestamp": int(
                funding.funding_time.timestamp() * 1_000
            ),
            "funding_datetime": (
                funding.funding_time.isoformat()
            ),
            "mark_price": funding.mark_price,
        }

    @staticmethod
    def _trade_to_dict(trade: BingXTrade) -> dict[str, Any]:
        return {
            "id": str(trade.trade_id),
            "price": trade.price,
            "amount": trade.quantity,
            "side": trade.side.value.casefold(),
            "timestamp": int(
                trade.timestamp.timestamp() * 1_000
            ),
            "datetime": trade.timestamp.isoformat(),
        }

    @staticmethod
    def _merge_order_options(
        params: Mapping[str, Any] | None,
        kwargs: Mapping[str, Any],
    ) -> dict[str, Any]:
        if params is None:
            options: dict[str, Any] = {}
        elif isinstance(params, Mapping):
            options = dict(params)
        else:
            raise TypeError("params must be a mapping or None.")

        duplicates = set(options).intersection(kwargs)

        if duplicates:
            names = ", ".join(sorted(duplicates))
            raise ValueError(
                f"Duplicate order parameters: {names}"
            )

        options.update(kwargs)
        return options

    @staticmethod
    def _pop_alias(
        options: dict[str, Any],
        snake_name: str,
        camel_name: str,
        *,
        default: Any,
    ) -> Any:
        has_snake = snake_name in options
        has_camel = camel_name in options

        if has_snake and has_camel:
            raise ValueError(
                f"Use only one of {snake_name} or {camel_name}."
            )

        if has_snake:
            return options.pop(snake_name)

        if has_camel:
            return options.pop(camel_name)

        return default

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

    @classmethod
    def _order_side(
        cls,
        value: str,
    ) -> BingXOrderSide:
        normalized = cls._required_text(
            value,
            field_name="side",
        ).upper()

        try:
            return BingXOrderSide(normalized)
        except ValueError as exc:
            raise ValueError(
                "side must be BUY or SELL."
            ) from exc

    @classmethod
    def _order_type(
        cls,
        value: str,
    ) -> BingXOrderType:
        normalized = cls._required_text(
            value,
            field_name="order_type",
        ).upper()

        try:
            return BingXOrderType(normalized)
        except ValueError as exc:
            allowed = ", ".join(
                item.value for item in BingXOrderType
            )
            raise ValueError(
                f"Unsupported order_type: {value!r}. "
                f"Allowed values: {allowed}"
            ) from exc

    @classmethod
    def _position_side(
        cls,
        value: str,
    ) -> BingXPositionSide:
        normalized = cls._required_text(
            value,
            field_name="position_side",
        ).upper()

        try:
            return BingXPositionSide(normalized)
        except ValueError as exc:
            raise ValueError(
                "position_side must be LONG, SHORT, or BOTH."
            ) from exc

    @classmethod
    def _time_in_force(
        cls,
        value: str,
    ) -> BingXTimeInForce:
        normalized = cls._required_text(
            value,
            field_name="time_in_force",
        ).upper()

        try:
            return BingXTimeInForce(normalized)
        except ValueError as exc:
            raise ValueError(
                "time_in_force must be GTC, IOC, FOK, or GTX."
            ) from exc

    @staticmethod
    def _positive_decimal(
        value: Any,
        *,
        field_name: str,
    ) -> Decimal:
        if isinstance(value, bool):
            raise TypeError(f"{field_name} must be numeric.")

        try:
            normalized = Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise TypeError(
                f"{field_name} must be numeric."
            ) from exc

        if not normalized.is_finite():
            raise ValueError(f"{field_name} must be finite.")

        if normalized <= 0:
            raise ValueError(
                f"{field_name} must be greater than zero."
            )

        return normalized

    @classmethod
    def _optional_positive_decimal(
        cls,
        value: Any,
        *,
        field_name: str,
    ) -> Decimal | None:
        if value is None:
            return None

        return cls._positive_decimal(
            value,
            field_name=field_name,
        )

    @staticmethod
    def _positive_integer(
        value: Any,
        *,
        field_name: str,
    ) -> int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError(f"{field_name} must be an integer.")

        if value <= 0:
            raise ValueError(
                f"{field_name} must be greater than zero."
            )

        return value

    @staticmethod
    def _positive_float(
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

        if not 0 < normalized < float("inf"):
            raise ValueError(
                f"{field_name} must be finite and greater than zero."
            )

        return normalized


__all__ = (
    "BingXAdapter",
    "ClientFactory",
)