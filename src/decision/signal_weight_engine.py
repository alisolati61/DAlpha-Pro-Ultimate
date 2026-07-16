from __future__ import annotations

from dataclasses import dataclass

from src.analysis.market_regime import MarketRegime


@dataclass(slots=True)
class WeightedSignal:

    source: str

    score: float

    weight: float

    final_score: float


class SignalWeightEngine:
    """
    Assign weights to signals depending on
    current market regime.
    """

    def weight_signal(
        self,
        source: str,
        score: float,
        regime: MarketRegime,
    ) -> WeightedSignal:

        weight = 1.0

        if regime == MarketRegime.TRENDING_UP:

            if source in {
                "EMA",
                "MACD",
                "BOS",
                "CHOCH",
            }:
                weight = 1.30

        elif regime == MarketRegime.TRENDING_DOWN:

            if source in {
                "EMA",
                "MACD",
                "BOS",
                "CHOCH",
            }:
                weight = 1.30

        elif regime == MarketRegime.RANGING:

            if source in {
                "RSI",
                "FVG",
                "OrderBlock",
            }:
                weight = 1.25

        elif regime == MarketRegime.VOLATILE:

            weight = 0.85

        return WeightedSignal(
            source=source,
            score=score,
            weight=weight,
            final_score=score * weight,
        )