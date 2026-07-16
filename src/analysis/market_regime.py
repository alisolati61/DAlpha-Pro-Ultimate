from __future__ import annotations

from enum import Enum

from src.domain.candle_series import CandleSeries


class MarketRegime(Enum):
    TRENDING_UP = "TRENDING_UP"
    TRENDING_DOWN = "TRENDING_DOWN"
    RANGING = "RANGING"
    VOLATILE = "VOLATILE"


class MarketRegimeEngine:
    """
    Foundation Market Regime detector.
    """

    def detect(
        self,
        series: CandleSeries,
    ) -> MarketRegime:

        if len(series.candles) < 20:
            return MarketRegime.RANGING

        closes = [c.close for c in series.candles[-20:]]

        change = closes[-1] - closes[0]

        volatility = max(closes) - min(closes)

        if volatility > abs(change) * 3:
            return MarketRegime.VOLATILE

        if change > 0:
            return MarketRegime.TRENDING_UP

        if change < 0:
            return MarketRegime.TRENDING_DOWN

        return MarketRegime.RANGING