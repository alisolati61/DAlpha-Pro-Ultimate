from src.ai.market_regime import (
    MarketContext,
    MarketRegime,
    MarketRegimeAnalyzer,
)


def test_detect_bull_market():

    analyzer = MarketRegimeAnalyzer()

    result = analyzer.analyze(
        MarketContext(
            trend_score=85,
            volatility_score=40,
            volume_score=50,
            momentum_score=60,
        )
    )

    assert result.regime == MarketRegime.BULL


def test_detect_bear_market():

    analyzer = MarketRegimeAnalyzer()

    result = analyzer.analyze(
        MarketContext(
            trend_score=20,
            volatility_score=40,
            volume_score=50,
            momentum_score=40,
        )
    )

    assert result.regime == MarketRegime.BEAR


def test_detect_high_volatility():

    analyzer = MarketRegimeAnalyzer()

    result = analyzer.analyze(
        MarketContext(
            trend_score=50,
            volatility_score=90,
            volume_score=50,
            momentum_score=50,
        )
    )

    assert result.regime == MarketRegime.HIGH_VOLATILITY


def test_detect_low_volatility():

    analyzer = MarketRegimeAnalyzer()

    result = analyzer.analyze(
        MarketContext(
            trend_score=50,
            volatility_score=10,
            volume_score=50,
            momentum_score=50,
        )
    )

    assert result.regime == MarketRegime.LOW_VOLATILITY


def test_detect_breakout():

    analyzer = MarketRegimeAnalyzer()

    result = analyzer.analyze(
        MarketContext(
            trend_score=50,
            volatility_score=50,
            volume_score=90,
            momentum_score=80,
        )
    )

    assert result.regime == MarketRegime.BREAKOUT


def test_detect_accumulation():

    analyzer = MarketRegimeAnalyzer()

    result = analyzer.analyze(
        MarketContext(
            trend_score=50,
            volatility_score=50,
            volume_score=80,
            momentum_score=30,
        )
    )

    assert result.regime == MarketRegime.ACCUMULATION


def test_detect_sideways():

    analyzer = MarketRegimeAnalyzer()

    result = analyzer.analyze(
        MarketContext(
            trend_score=50,
            volatility_score=50,
            volume_score=50,
            momentum_score=50,
        )
    )

    assert result.regime == MarketRegime.SIDEWAYS