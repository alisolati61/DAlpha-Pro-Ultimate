from __future__ import annotations

import ccxt.async_support as ccxt

from src.exchange.base import BaseExchange


class CCXTExchange(BaseExchange):

    def __init__(
        self,
        exchange_name: str,
        **config,
    ) -> None:

        exchange_class = getattr(
            ccxt,
            exchange_name,
        )

        self.exchange = exchange_class(config)

    # ------------------------------------------------

    async def connect(self) -> None:

        await self.exchange.load_markets()

    # ------------------------------------------------

    async def disconnect(self) -> None:

        await self.exchange.close()

    # ------------------------------------------------

    async def health_check(self) -> bool:

        try:

            await self.exchange.fetch_time()

            return True

        except Exception:

            return False

    # ------------------------------------------------

    async def fetch_balance(self):

        return await self.exchange.fetch_balance()

    # ------------------------------------------------

    async def fetch_positions(self):

        if hasattr(
            self.exchange,
            "fetch_positions",
        ):

            return await self.exchange.fetch_positions()

        return []

    # ------------------------------------------------

    async def fetch_ticker(
        self,
        symbol: str,
    ):

        return await self.exchange.fetch_ticker(
            symbol,
        )

    # ------------------------------------------------

    async def fetch_orderbook(
        self,
        symbol: str,
    ):

        return await self.exchange.fetch_order_book(
            symbol,
        )

    # ------------------------------------------------

    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 500,
    ):

        return await self.exchange.fetch_ohlcv(
            symbol,
            timeframe,
            limit=limit,
        )

    # ------------------------------------------------

    async def create_order(
        self,
        *args,
        **kwargs,
    ):

        return await self.exchange.create_order(
            *args,
            **kwargs,
        )

    # ------------------------------------------------

    async def cancel_order(
        self,
        order_id: str,
    ):

        return await self.exchange.cancel_order(
            order_id,
        )

    # ------------------------------------------------

    async def fetch_order(
        self,
        order_id: str,
        symbol: str | None = None,
    ):

        return await self.exchange.fetch_order(
            order_id,
            symbol,
        )