import pytest

from src.core.asset_scorer import AssetScorer
from src.market.market_data import MarketData


def test_asset_score():

    market = MarketData(
        symbol="BTC/USDT",
        last_price=100.00,
        bid=99.95,
        ask=100.05,
        volume=1_000_000,
    )

    scorer = AssetScorer()

    asset = scorer.score(
        market,
        reference_volume=1_000_000,
    )

    # Final score should be greater than zero
    assert asset.score > 0

    # Volume score should be maximum
    assert asset.volume_score == pytest.approx(100.0)

    # Liquidity score should be maximum
    assert asset.liquidity_score == pytest.approx(100.0)

    # Trend score should be around the middle
    assert asset.trend_score == pytest.approx(50.0)

    # Confidence must be between 0 and 1
    assert 0.0 <= asset.confidence <= 1.0