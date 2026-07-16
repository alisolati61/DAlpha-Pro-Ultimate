from __future__ import annotations

from collections import defaultdict
from typing import Callable

from src.domain.market_data import MarketData


class MarketDataRouter:
    """
    Routes market data to subscribed handlers.
    """

    def __init__(self) -> None:
        self._subscribers: dict[str, list[Callable[[MarketData], None]]] = defaultdict(list)

    def subscribe(
        self,
        symbol: str,
        callback: Callable[[MarketData], None],
    ) -> None:

        self._subscribers[symbol].append(callback)

    def publish(
        self,
        data: MarketData,
    ) -> None:

        for callback in self._subscribers.get(data.symbol, []):
            callback(data)

    def subscriber_count(
        self,
        symbol: str,
    ) -> int:

        return len(self._subscribers.get(symbol, []))