"""Asynchronous CCXT adapter with deterministic lifecycle management."""

from __future__ import annotations

import asyncio
from typing import Any

import ccxt.async_support as ccxt

from src.exchange.base import BaseExchange


class CCXTExchange(BaseExchange):
    """Adapt a CCXT asynchronous client to the project's exchange contract."""

    def __init__(
        self,
        exchange_name: str,
        *,
        health_check_timeout: float = 10.0,
        **config: Any,
    ) -> None:
        normalized_name = exchange_name.strip().lower()
        exchange_class = getattr(ccxt, normalized_name, None)

        if not normalized_name or not callable(exchange_class):
            raise ValueError(
                f"Unsupported CCXT exchange: {exchange_name}"
            )

        if health_check_timeout <= 0:
            raise ValueError(
                "health_check_timeout must be greater than zero"
            )

        self.exchange_name = normalized_name
        self.exchange = exchange_class(dict(config))

        self._health_check_timeout = float(health_check_timeout)
        self._connected = False
        self._lifecycle_lock = asyncio.Lock()

    @property
    def is_connected(self) -> bool:
        """Return the adapter's local lifecycle state."""

        return self._connected

    async def connect(self) -> None:
        """Load markets exactly once for the active lifecycle."""

        async with self._lifecycle_lock:
            if self._connected:
                return

            try:
                await self.exchange.load_markets()
            except BaseException:
                await self._close_after_failed_connect()
                raise

            self._connected = True

    async def disconnect(self) -> None:
        """Close the CCXT client exactly once for the active lifecycle."""

        async with self._lifecycle_lock:
            if not self._connected:
                return

            try:
                await self.exchange.close()
            finally:
                self._connected = False

    async def health_check(self) -> bool:
        """Return whether the connected exchange responds within the timeout."""

        if not self._connected:
            return False

        probe = getattr(self.exchange, "fetch_time", None)

        if not callable(probe):
            probe = getattr(self.exchange, "fetch_status", None)

        if not callable(probe):
            return False

        try:
            async with asyncio.timeout(self._health_check_timeout):
                await probe()
        except Exception:
            return False

        return True

    async def fetch_balance(self) -> Any:
        """Fetch account balances through CCXT."""

        return await self.exchange.fetch_balance()

    async def fetch_positions(self) -> Any:
        """Fetch open positions when the selected exchange supports them."""

        fetch_positions = getattr(
            self.exchange,
            "fetch_positions",
            None,
        )

        if not callable(fetch_positions):
            return []

        return await fetch_positions()

    async def fetch_ticker(self, symbol: str) -> Any:
        """Fetch the latest ticker for a normalized CCXT symbol."""

        return await self.exchange.fetch_ticker(symbol)

    async def fetch_orderbook(self, symbol: str) -> Any:
        """Fetch the current order book for a normalized CCXT symbol."""

        return await self.exchange.fetch_order_book(symbol)

    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 500,
    ) -> Any:
        """Fetch OHLCV candles through CCXT."""

        return await self.exchange.fetch_ohlcv(
            symbol,
            timeframe,
            limit=limit,
        )

    async def create_order(
        self,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Create an order through CCXT."""

        return await self.exchange.create_order(
            *args,
            **kwargs,
        )

    async def cancel_order(self, order_id: str) -> Any:
        """Cancel an order through CCXT."""

        return await self.exchange.cancel_order(order_id)

    async def fetch_order(
        self,
        order_id: str,
        symbol: str | None = None,
    ) -> Any:
        """Fetch an order through CCXT."""

        return await self.exchange.fetch_order(
            order_id,
            symbol,
        )

    async def _close_after_failed_connect(self) -> None:
        """Best-effort cleanup without masking the original connect error."""

        close = getattr(self.exchange, "close", None)

        if not callable(close):
            return

        try:
            await close()
        except Exception:
            pass


__all__ = ("CCXTExchange",)