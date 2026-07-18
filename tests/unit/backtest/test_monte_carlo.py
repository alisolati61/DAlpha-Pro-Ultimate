from src.ai.performance_tracker import TradePerformance
from src.backtesting.monte_carlo import (
    MonteCarloEngine,
    MonteCarloResult,
)


def trade(pnl: float):

    return TradePerformance(
        strategy="SMC",
        symbol="BTCUSDT",
        timeframe="1h",
        pnl=float(pnl),
        risk_reward=2.0,
        win=pnl > 0,
        confidence=80.0,
        duration_minutes=60,
    )


def test_empty():

    engine = MonteCarloEngine()

    result = engine.run([])

    assert isinstance(result, MonteCarloResult)

    assert result.simulations == 0


def test_simulation_runs():

    engine = MonteCarloEngine()

    result = engine.run(
        [
            trade(100),
            trade(-50),
            trade(80),
        ],
        simulations=100,
    )

    assert result.simulations == 100


def test_average_profit_type():

    engine = MonteCarloEngine()

    result = engine.run(
        [
            trade(10),
            trade(20),
        ],
        simulations=50,
    )

    assert isinstance(result.average_profit, float)


def test_best_profit():

    engine = MonteCarloEngine()

    result = engine.run(
        [
            trade(10),
            trade(20),
            trade(-5),
        ],
        simulations=100,
    )

    assert result.best_profit >= result.worst_profit


def test_result_types():

    engine = MonteCarloEngine()

    result = engine.run(
        [
            trade(10),
        ],
        simulations=10,
    )

    assert isinstance(result.average_profit, float)

    assert isinstance(result.best_profit, float)

    assert isinstance(result.worst_profit, float)