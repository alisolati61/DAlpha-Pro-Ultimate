from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class MarketRegime(str, Enum):
    """
    Supported market regimes.
    """

    BULL = "bull"
    BEAR = "bear"
    SIDEWAYS = "sideways"

    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"

    ACCUMULATION = "accumulation"
    DISTRIBUTION = "distribution"

    BREAKOUT = "breakout"
    UNKNOWN = "unknown"


@dataclass(slots=True)
class MarketContext:
    """
    Current market measurements.
    """

    trend_score: float
    volatility_score: float
    volume_score: float
    momentum_score: float


@dataclass(slots=True)
class MarketRegimeResult:
    """
    Output of MarketRegimeAnalyzer.
    """

    regime: MarketRegime
    confidence: float
    reason: str


class MarketRegimeAnalyzer:
    """
    Detects current market regime.

    Future versions:

    - ATR
    - ADX
    - VIX
    - OrderFlow
    - Smart Money
    - AI Classification
    """

    def analyze(
        self,
        context: MarketContext,
    ) -> MarketRegimeResult:

        # -----------------------------
        # Trend
        # -----------------------------
        if context.trend_score >= 70:

            return MarketRegimeResult(
                regime=MarketRegime.BULL,
                confidence=context.trend_score,
                reason="Strong bullish trend",
            )

        if context.trend_score <= 30:

            return MarketRegimeResult(
                regime=MarketRegime.BEAR,
                confidence=100 - context.trend_score,
                reason="Strong bearish trend",
            )

        # -----------------------------
        # Volatility
        # -----------------------------
        if context.volatility_score >= 80:

            return MarketRegimeResult(
                regime=MarketRegime.HIGH_VOLATILITY,
                confidence=context.volatility_score,
                reason="High market volatility",
            )

        if context.volatility_score <= 20:

            return MarketRegimeResult(
                regime=MarketRegime.LOW_VOLATILITY,
                confidence=100 - context.volatility_score,
                reason="Low market volatility",
            )

        # -----------------------------
        # Volume Analysis
        # -----------------------------
        if (
            context.volume_score >= 80
            and context.momentum_score >= 70
        ):

            return MarketRegimeResult(
                regime=MarketRegime.BREAKOUT,
                confidence=85.0,
                reason="High volume breakout",
            )

        if (
            context.volume_score >= 70
            and context.momentum_score <= 40
        ):

            return MarketRegimeResult(
                regime=MarketRegime.ACCUMULATION,
                confidence=75.0,
                reason="Accumulation detected",
            )

        if (
            context.volume_score >= 70
            and context.momentum_score >= 90
        ):

            return MarketRegimeResult(
                regime=MarketRegime.DISTRIBUTION,
                confidence=75.0,
                reason="Distribution detected",
            )

        # -----------------------------
        # Default
        # -----------------------------
        return MarketRegimeResult(
            regime=MarketRegime.SIDEWAYS,
            confidence=60.0,
            reason="Range market",
        )