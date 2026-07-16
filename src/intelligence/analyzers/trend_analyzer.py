from src.market.market_data import MarketData


class TrendAnalyzer:
    """
    Basic trend analysis.
    """

    @staticmethod
    def is_bullish(
        market: MarketData,
    ) -> bool:
        return market.last_price > market.bid

    @staticmethod
    def trend_score(
        market: MarketData,
    ) -> float:

        spread = market.ask - market.bid

        if spread <= 0:
            return 0.0

        score = ((market.last_price - market.bid) / spread) * 100

        return max(0.0, min(score, 100.0))