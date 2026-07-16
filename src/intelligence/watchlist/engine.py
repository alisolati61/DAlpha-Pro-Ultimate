from typing import List

from src.market.market_data import MarketData


class WatchlistEngine:
    """
    Holds approved trading candidates.
    """

    def __init__(self):
        self._watchlist: List[MarketData] = []

    def add(self, market: MarketData) -> None:
        self._watchlist.append(market)

    def clear(self) -> None:
        self._watchlist.clear()

    def get_all(self) -> List[MarketData]:
        return self._watchlist.copy()

    def count(self) -> int:
        return len(self._watchlist)