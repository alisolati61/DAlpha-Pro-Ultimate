from typing import List

from src.market.market_data import MarketData


class TrendDiscoveryEngine:
    """
    Discovers high-quality trading candidates.
    """

    def __init__(self):
        self.candidates: List[MarketData] = []

    def clear(self) -> None:
        self.candidates.clear()

    def add(self, market: MarketData) -> None:
        self.candidates.append(market)

    def filter_by_volume(
        self,
        minimum_volume: float,
    ) -> List[MarketData]:

        return [
            market
            for market in self.candidates
            if market.volume >= minimum_volume
        ]

    def get_candidates(self) -> List[MarketData]:
        return self.candidates.copy()