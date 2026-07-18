from __future__ import annotations

from typing import Any

from src.exchange.ccxt_exchange import CCXTExchange


class CryptoConnector:
    """
    High-level facade over CCXTExchange.

    This class hides exchange implementation details
    from the rest of the project.
    """

    def __init__(
        self,
        exchange_name: str = "bingx",
        **config,
    ) -> None:

        self.exchange = CCXTExchange(
            exchange_name,
            **config,
        )

    # --------------------------------------------------

    async def connect(self) -> None:

        await self.exchange.connect()

    # --------------------------------------------------

    async def disconnect(self) -> None:

        await self.exchange.disconnect()

    # --------------------------------------------------

    async def health(self) -> bool:

        return await self.exchange.health_check()

    # --------------------------------------------------

    async def get_balance(self) -> Any:

        return await self.exchange.fetch_balance()

    # --------------------------------------------------

    async def get_positions(self) -> Any:

        return await self.exchange.fetch_positions()

    # --------------------------------------------------

    async def get_ticker(
        self,
        symbol: str,
    ) -> Any:

        return await self.exchange.fetch_ticker(symbol)

    # --------------------------------------------------

    async def get_orderbook(
        self,
        symbol: str,
    ) -> Any:

        return await self.exchange.fetch_orderbook(symbol)

    # --------------------------------------------------

    async def get_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 500,
    ) -> Any:

        return await self.exchange.fetch_ohlcv(
            symbol,
            timeframe,
            limit,
        )

    # --------------------------------------------------

    async def create_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        amount: float,
        price: float | None = None,
    ) -> Any:

        return await self.exchange.create_order(
            symbol,
            order_type,
            side,
            amount,
            price,
        )

    # --------------------------------------------------

    async def cancel_order(
        self,
        order_id: str,
    ) -> Any:

        return await self.exchange.cancel_order(
            order_id,
        )

    # --------------------------------------------------

    async def fetch_order(
        self,
        order_id: str,
        symbol: str | None = None,
    ) -> Any:

        return await self.exchange.fetch_order(
            order_id,
            symbol,
        )