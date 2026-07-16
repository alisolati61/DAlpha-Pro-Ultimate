from src.market.market_data import MarketData


class MarketAnalyzer:
    """
    Performs basic market quality analysis.
    """

    @staticmethod
    def spread(market: MarketData) -> float:
        return market.ask - market.bid

    @staticmethod
    def spread_percent(market: MarketData) -> float:

        if market.last_price == 0:
            return 0.0

        return ((market.ask - market.bid) / market.last_price) * 100

    @staticmethod
    def is_liquid(
        market: MarketData,
        max_spread_percent: float = 0.20,
    ) -> bool:

        return (
            market.volume > 0
            and MarketAnalyzer.spread_percent(market)
            <= max_spread_percent
        )