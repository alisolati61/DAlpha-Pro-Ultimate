from __future__ import annotations

from abc import ABC, abstractmethod

from src.data.market_data import MarketData


class MarketDataFeed(ABC):
    """
    Base interface for every market data provider.

    Future implementations:
    - BinanceFeed
    - BybitFeed
    - OKXFeed
    - KuCoinFeed
    - PaperFeed
    """

    @abstractmethod
    def connect(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def disconnect(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def is_connected(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def subscribe(
        self,
        symbol: str,
        timeframe: str,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def unsubscribe(
        self,
        symbol: str,
        timeframe: str,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def latest(
        self,
        symbol: str,
        timeframe: str,
    ) -> MarketData:
        raise NotImplementedError