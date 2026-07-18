from src.ai.performance_tracker import (
    PerformanceTracker,
    TradePerformance,
)


def test_tracker_initial_state():

    tracker = PerformanceTracker()

    assert tracker.trades == 0
    assert tracker.wins == 0
    assert tracker.losses == 0
    assert tracker.win_rate == 0.0


def test_add_trade():

    tracker = PerformanceTracker()

    tracker.add(
        TradePerformance(
            strategy="SMC",
            symbol="BTCUSDT",
            timeframe="1h",
            pnl=120.0,
            risk_reward=2.5,
            win=True,
            confidence=82.0,
            duration_minutes=45,
        )
    )

    assert tracker.trades == 1
    assert tracker.wins == 1
    assert tracker.losses == 0


def test_total_profit():

    tracker = PerformanceTracker()

    tracker.add(
        TradePerformance(
            strategy="SMC",
            symbol="BTCUSDT",
            timeframe="1h",
            pnl=100,
            risk_reward=2,
            win=True,
            confidence=80,
            duration_minutes=20,
        )
    )

    tracker.add(
        TradePerformance(
            strategy="SMC",
            symbol="ETHUSDT",
            timeframe="4h",
            pnl=-50,
            risk_reward=1,
            win=False,
            confidence=60,
            duration_minutes=50,
        )
    )

    assert tracker.total_profit == 50


def test_win_rate():

    tracker = PerformanceTracker()

    tracker.add(
        TradePerformance(
            strategy="A",
            symbol="BTC",
            timeframe="1h",
            pnl=10,
            risk_reward=2,
            win=True,
            confidence=70,
            duration_minutes=10,
        )
    )

    tracker.add(
        TradePerformance(
            strategy="A",
            symbol="BTC",
            timeframe="1h",
            pnl=-5,
            risk_reward=1,
            win=False,
            confidence=50,
            duration_minutes=10,
        )
    )

    assert tracker.win_rate == 50.0


def test_strategy_filter():

    tracker = PerformanceTracker()

    tracker.add(
        TradePerformance(
            strategy="SMC",
            symbol="BTC",
            timeframe="1h",
            pnl=20,
            risk_reward=2,
            win=True,
            confidence=80,
            duration_minutes=10,
        )
    )

    tracker.add(
        TradePerformance(
            strategy="ICT",
            symbol="BTC",
            timeframe="1h",
            pnl=15,
            risk_reward=2,
            win=True,
            confidence=70,
            duration_minutes=10,
        )
    )

    smc = tracker.by_strategy("SMC")

    assert len(smc) == 1
    assert smc[0].strategy == "SMC"


def test_clear_tracker():

    tracker = PerformanceTracker()

    tracker.add(
        TradePerformance(
            strategy="SMC",
            symbol="BTC",
            timeframe="1h",
            pnl=10,
            risk_reward=2,
            win=True,
            confidence=80,
            duration_minutes=10,
        )
    )

    tracker.clear()

    assert tracker.trades == 0