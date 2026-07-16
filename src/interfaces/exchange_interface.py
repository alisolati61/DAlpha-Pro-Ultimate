from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from src.domain.order import Order


class ExchangeInterface(ABC):
    """
    Base contract for every exchange adapter.

    Every exchange implementation
    (Binance, Bybit, OKX, KuCoin, Paper Trading...)
    must implement this interface.
    """

    @abstractmethod
    def connect(self) -> None:
        """Open exchange connection."""
        raise NotImplementedError

    @abstractmethod
    def disconnect(self) -> None:
        """Close exchange connection."""
        raise NotImplementedError

    @abstractmethod
    def health_check(self) -> bool:
        """Check exchange availability."""
        raise NotImplementedError

    @abstractmethod
    def get_balance(self) -> Any:
        """Return wallet balance."""
        raise NotImplementedError

    @abstractmethod
    def get_positions(self) -> Any:
        """Return open positions."""
        raise NotImplementedError

    @abstractmethod
    def place_order(self, order: Order) -> Any:
        """Send a new order."""
        raise NotImplementedError

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an existing order."""
        raise NotImplementedError

    @abstractmethod
    def get_order_status(self, order_id: str) -> Any:
        """Return order status."""
        raise NotImplementedError

    @abstractmethod
    def get_ticker(self, symbol: str) -> Any:
        """Return latest ticker."""
        raise NotImplementedError

    @abstractmethod
    def get_orderbook(self, symbol: str) -> Any:
        """Return current orderbook."""
        raise NotImplementedError

    @abstractmethod
    def get_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 500,
    ) -> Any:
        """Return historical candles."""
        raise NotImplementedError