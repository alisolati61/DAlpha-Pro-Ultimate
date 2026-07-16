from dataclasses import dataclass

from src.market.market_data import MarketData


@dataclass(slots=True)
class ScoredAsset:
    market: MarketData

    score: float

    trend_score: float = 0.0

    volume_score: float = 0.0

    liquidity_score: float = 0.0

    volatility_score: float = 0.0

    confidence: float = 0.0