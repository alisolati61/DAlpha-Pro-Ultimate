from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseExchange(ABC):
    """
    Base contract for every exchange adapter.

    Every implementation (CCXT, REST, WebSocket, Paper...)
    must follow this interface.
    """

    @abstractmethod
    async def connect(self) -> None:
        """Open exchange connection."""
        raise NotImplementedError

    @abstractmethod
    async def disconnect(self) -> None:
        """Close exchange connection."""
        raise NotImplementedError

    @abstractmethod
    async def health_check(self) -> bool:
        """Verify exchange availability."""
        raise NotImplementedError

    @abstractmethod
    async def fetch_ticker(
        self,
        symbol: str,
    ) -> Any:
        raise NotImplementedError

    @abstractmethod
    async def fetch_balance(self) -> Any:
        raise NotImplementedError

    @abstractmethod
    async def fetch_positions(self) -> Any:
        raise NotImplementedError

    @abstractmethod
    async def fetch_orderbook(
        self,
        symbol: str,
    ) -> Any:
        raise NotImplementedError

    @abstractmethod
    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 500,
    ) -> Any:
        raise NotImplementedError

    @abstractmethod
    async def create_order(
        self,
        *args,
        **kwargs,
    ) -> Any:
        raise NotImplementedError

    @abstractmethod
    async def cancel_order(
        self,
        order_id: str,
    ) -> Any:
        raise NotImplementedError

    @abstractmethod
    async def fetch_order(
        self,
        order_id: str,
        symbol: str | None = None,
    ) -> Any:
        raise NotImplementedError