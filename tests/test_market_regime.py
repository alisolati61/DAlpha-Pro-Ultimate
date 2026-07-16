from src.core.market_regime import (
    MarketRegime,
    MarketRegimeDetector,
)


def test_market_regime_detector():
    detector = MarketRegimeDetector()

    trending = detector.detect(atr=1.2, adx=30)
    ranging = detector.detect(atr=1.0, adx=15)
    high_volatility = detector.detect(atr=4.5, adx=35)

    # بررسی نوع خروجی
    assert isinstance(trending, MarketRegime)
    assert isinstance(ranging, MarketRegime)
    assert isinstance(high_volatility, MarketRegime)

    # بررسی مقدار دقیق خروجی
    assert trending == MarketRegime.TRENDING
    assert ranging == MarketRegime.RANGING
    assert high_volatility == MarketRegime.HIGH_VOLATILITY