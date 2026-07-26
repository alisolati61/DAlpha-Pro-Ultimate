"""Stable asynchronous contract for exchange adapters.

Concrete adapters must implement every abstract operation. The base class also
provides an asynchronous context-manager lifecycle:

    async with exchange:
        ...

Entering awaits ``connect`` and leaving always awaits ``disconnect``. Exceptions
raised inside the context are never suppressed.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from types import TracebackType
from typing import Any, Self


class BaseExchange(ABC):
    """Abstract asynchronous interface implemented by exchange adapters."""

    @abstractmethod
    async def connect(self) -> None:
        """Open the exchange connection."""

        raise NotImplementedError

    @abstractmethod
    async def disconnect(self) -> None:
        """Close the exchange connection."""

        raise NotImplementedError

    @abstractmethod
    async def health_check(self) -> bool:
        """Return whether the exchange is currently available."""

        raise NotImplementedError

    @abstractmethod
    async def fetch_ticker(
        self,
        symbol: str,
    ) -> Any:
        """Fetch the latest ticker for ``symbol``."""

        raise NotImplementedError

    @abstractmethod
    async def fetch_balance(self) -> Any:
        """Fetch account balances."""

        raise NotImplementedError

    @abstractmethod
    async def fetch_positions(self) -> Any:
        """Fetch open positions."""

        raise NotImplementedError

    @abstractmethod
    async def fetch_orderbook(
        self,
        symbol: str,
    ) -> Any:
        """Fetch the order book for ``symbol``."""

        raise NotImplementedError

    @abstractmethod
    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 500,
    ) -> Any:
        """Fetch OHLCV candles."""

        raise NotImplementedError

    @abstractmethod
    async def create_order(
        self,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Create an exchange order."""

        raise NotImplementedError

    @abstractmethod
    async def cancel_order(
        self,
        order_id: str,
    ) -> Any:
        """Cancel an exchange order."""

        raise NotImplementedError

    @abstractmethod
    async def fetch_order(
        self,
        order_id: str,
        symbol: str | None = None,
    ) -> Any:
        """Fetch one exchange order."""

        raise NotImplementedError

    async def __aenter__(self) -> Self:
        """Connect and return this adapter."""

        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        """Disconnect without suppressing context exceptions."""

        await self.disconnect()
        return False

    @classmethod
    def required_methods(cls) -> tuple[str, ...]:
        """Return the deterministic abstract-method contract."""

        return tuple(
            sorted(cls.__abstractmethods__)
        )


__all__ = ("BaseExchange",)