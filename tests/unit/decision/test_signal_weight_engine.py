from src.analysis.market_regime import MarketRegime
from src.decision.signal_weight_engine import SignalWeightEngine


def test_trend_weight():

    signal = SignalWeightEngine().weight_signal(

        "EMA",

        80,

        MarketRegime.TRENDING_UP,

    )

    assert signal.weight > 1.0

    assert signal.final_score > 80


def test_range_weight():

    signal = SignalWeightEngine().weight_signal(

        "RSI",

        70,

        MarketRegime.RANGING,

    )

    assert signal.weight > 1.0


def test_volatile_weight():

    signal = SignalWeightEngine().weight_signal(

        "EMA",

        80,

        MarketRegime.VOLATILE,

    )

    assert signal.weight < 1.0