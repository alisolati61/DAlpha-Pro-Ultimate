from dataclasses import dataclass


@dataclass
class MarketRegimeResult:
    regime: str
    volatility: str
    recommendation: str


class MarketRegimeEngine:

    def detect(
        self,
        trend_strength: float,
        atr_percent: float,
    ) -> MarketRegimeResult:

        if trend_strength >= 70:

            regime = "TREND"

        elif trend_strength <= 30:

            regime = "RANGE"

        else:

            regime = "TRANSITION"

        if atr_percent >= 3:

            volatility = "HIGH"

        elif atr_percent >= 1:

            volatility = "MEDIUM"

        else:

            volatility = "LOW"

        if regime == "TREND":

            recommendation = "TREND_FOLLOWING"

        elif regime == "RANGE":

            recommendation = "MEAN_REVERSION"

        else:

            recommendation = "WAIT_CONFIRMATION"

        return MarketRegimeResult(
            regime=regime,
            volatility=volatility,
            recommendation=recommendation,
        )