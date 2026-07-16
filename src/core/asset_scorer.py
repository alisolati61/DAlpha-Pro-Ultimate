from src.domain.scored_asset import ScoredAsset
from src.market.market_data import MarketData
from src.domain.candle_series import CandleSeries

from src.intelligence.analyzers.market_analyzer import MarketAnalyzer
from src.intelligence.analyzers.trend_analyzer import TrendAnalyzer
from src.intelligence.analyzers.volume_analyzer import VolumeAnalyzer
from src.intelligence.analyzers.rsi_analyzer import RSIScorer


class AssetScorer:
    """
    Scores assets using multiple analyzers.

    Current Factors:
    - Volume
    - Trend
    - Liquidity
    - RSI

    Designed to be easily extended with:
    - EMA
    - MACD
    - ATR
    - Smart Money
    - Order Flow
    - OnChain
    """

    def score(
        self,
        market: MarketData,
        reference_volume: float,
        candles: CandleSeries | None = None,
    ) -> ScoredAsset:

        volume_score = VolumeAnalyzer.volume_score(
            market,
            reference_volume,
        )

        trend_score = TrendAnalyzer.trend_score(
            market,
        )

        liquidity_score = (
            100.0
            if MarketAnalyzer.is_liquid(market)
            else 0.0
        )

        # Default RSI score
        rsi_score = 50.0

        if candles is not None:
            rsi_score = RSIScorer.score(candles)

        # Final weighted score
        final_score = (
            volume_score * 0.35
            + trend_score * 0.30
            + liquidity_score * 0.15
            + rsi_score * 0.20
        )

        return ScoredAsset(
            market=market,
            score=round(final_score, 2),
            trend_score=trend_score,
            volume_score=volume_score,
            liquidity_score=liquidity_score,
            confidence=round(final_score / 100, 2),
        )