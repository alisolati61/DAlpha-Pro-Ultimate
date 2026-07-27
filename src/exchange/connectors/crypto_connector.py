"""High-level asynchronous facade over a concrete exchange adapter."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeAlias

from src.exchange.base import BaseExchange
from src.exchange.exchange_factory import ExchangeFactory, ExchangeType

ExchangeCreator: TypeAlias = Callable[..., BaseExchange]


class CryptoConnector(BaseExchange):
    """Own one exchange adapter and expose the project's stable async API."""

    def __init__(
        self,
        exchange_name: ExchangeType | str = ExchangeType.BINGX,
        *,
        exchange: BaseExchange | None = None,
        factory: ExchangeCreator | None = None,
        **config: Any,
    ) -> None:
        if exchange is not None:
            if not isinstance(exchange, BaseExchange):
                raise TypeError(
                    "exchange must implement the BaseExchange contract."
                )

            if config:
                raise ValueError(
                    "config cannot be supplied when exchange is injected."
                )

            if factory is not None:
                raise ValueError(
                    "factory cannot be supplied when exchange is injected."
                )

            self.exchange = exchange
            self.exchange_name = self._resolve_injected_name(
                exchange_name,
                exchange,
            )
            return

        normalized_name = self._normalize_exchange_name(exchange_name)
        creator = ExchangeFactory.create if factory is None else factory

        if not callable(creator):
            raise TypeError("factory must be callable or None.")

        created = creator(exchange_name, **config)

        if not isinstance(created, BaseExchange):
            raise TypeError(
                "factory must return a BaseExchange instance."
            )

        self.exchange = created
        self.exchange_name = normalized_name

    async def connect(self) -> None:
        """Connect the owned exchange adapter."""

        await self.exchange.connect()

    async def disconnect(self) -> None:
        """Disconnect the owned exchange adapter."""

        await self.exchange.disconnect()

    async def health_check(self) -> bool:
        """Return the owned adapter's health state."""

        return await self.exchange.health_check()

    async def fetch_balance(self) -> Any:
        """Fetch account balances."""

        return await self.exchange.fetch_balance()

    async def fetch_positions(self) -> Any:
        """Fetch open positions."""

        return await self.exchange.fetch_positions()

    async def fetch_ticker(self, symbol: str) -> Any:
        """Fetch the latest ticker."""

        return await self.exchange.fetch_ticker(symbol)

    async def fetch_orderbook(self, symbol: str) -> Any:
        """Fetch the current order book."""

        return await self.exchange.fetch_orderbook(symbol)

    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 500,
    ) -> Any:
        """Fetch OHLCV candles."""

        return await self.exchange.fetch_ohlcv(
            symbol,
            timeframe,
            limit=limit,
        )

    async def create_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        amount: float,
        price: float | None = None,
        **params: Any,
    ) -> Any:
        """Create an order using the connector's stable argument order."""

        return await self.exchange.create_order(
            symbol,
            order_type,
            side,
            amount,
            price,
            **params,
        )

    async def cancel_order(self, order_id: str) -> Any:
        """Cancel an order."""

        return await self.exchange.cancel_order(order_id)

    async def fetch_order(
        self,
        order_id: str,
        symbol: str | None = None,
    ) -> Any:
        """Fetch one order."""

        return await self.exchange.fetch_order(order_id, symbol)

    async def health(self) -> bool:
        """Backward-compatible alias for :meth:`health_check`."""

        return await self.health_check()

    async def get_balance(self) -> Any:
        """Backward-compatible alias for :meth:`fetch_balance`."""

        return await self.fetch_balance()

    async def get_positions(self) -> Any:
        """Backward-compatible alias for :meth:`fetch_positions`."""

        return await self.fetch_positions()

    async def get_ticker(self, symbol: str) -> Any:
        """Backward-compatible alias for :meth:`fetch_ticker`."""

        return await self.fetch_ticker(symbol)

    async def get_orderbook(self, symbol: str) -> Any:
        """Backward-compatible alias for :meth:`fetch_orderbook`."""

        return await self.fetch_orderbook(symbol)

    async def get_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 500,
    ) -> Any:
        """Backward-compatible alias for :meth:`fetch_ohlcv`."""

        return await self.fetch_ohlcv(
            symbol,
            timeframe,
            limit=limit,
        )

    @staticmethod
    def _normalize_exchange_name(
        exchange_name: ExchangeType | str,
    ) -> str:
        if isinstance(exchange_name, ExchangeType):
            return exchange_name.value

        if not isinstance(exchange_name, str):
            raise TypeError(
                "exchange_name must be an ExchangeType or string."
            )

        normalized = exchange_name.strip().casefold()

        if not normalized:
            raise ValueError("exchange_name cannot be empty.")

        return normalized

    @classmethod
    def _resolve_injected_name(
        cls,
        exchange_name: ExchangeType | str,
        exchange: BaseExchange,
    ) -> str:
        adapter_name = getattr(exchange, "exchange_name", None)

        if isinstance(adapter_name, str) and adapter_name.strip():
            return adapter_name.strip().casefold()

        return cls._normalize_exchange_name(exchange_name)


__all__ = ("CryptoConnector", "ExchangeCreator")