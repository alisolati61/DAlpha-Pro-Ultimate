from src.market.market_data import MarketData


class VolumeAnalyzer:
    """
    Analyzes trading volume.
    """

    @staticmethod
    def is_high_volume(
        market: MarketData,
        minimum_volume: float,
    ) -> bool:
        return market.volume >= minimum_volume

    @staticmethod
    def volume_score(
        market: MarketData,
        reference_volume: float,
    ) -> float:

        if reference_volume <= 0:
            return 0.0

        score = (market.volume / reference_volume) * 100

        return min(score, 100.0)