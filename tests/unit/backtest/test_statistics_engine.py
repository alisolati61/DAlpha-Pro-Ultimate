from src.ai.performance_tracker import TradePerformance
from src.backtesting.statistics_engine import (
    BacktestStatistics,
    StatisticsEngine,
)


def trade(
    pnl: float,
):

    return TradePerformance(
        strategy="SMC",
        symbol="BTCUSDT",
        timeframe="1h",
        pnl=pnl,
        risk_reward=2.0,
        win=pnl > 0,
        confidence=80.0,
        duration_minutes=60,
    )


def test_empty_statistics():

    engine = StatisticsEngine()

    result = engine.calculate([])

    assert isinstance(result, BacktestStatistics)

    assert result.total_trades == 0

    assert result.net_profit == 0.0

    assert result.win_rate == 0.0


def test_trade_count():

    engine = StatisticsEngine()

    result = engine.calculate(
        [
            trade(100),
            trade(-50),
            trade(80),
        ]
    )

    assert result.total_trades == 3

    assert result.wins == 2

    assert result.losses == 1


def test_net_profit():

    engine = StatisticsEngine()

    result = engine.calculate(
        [
            trade(100),
            trade(-20),
            trade(50),
        ]
    )

    assert result.net_profit == 130.0


def test_win_rate():

    engine = StatisticsEngine()

    result = engine.calculate(
        [
            trade(100),
            trade(-50),
            trade(80),
            trade(-20),
        ]
    )

    assert result.win_rate == 50.0


def test_profit_factor():

    engine = StatisticsEngine()

    result = engine.calculate(
        [
            trade(100),
            trade(-50),
            trade(50),
        ]
    )

    assert result.profit_factor > 0


def test_drawdown():

    engine = StatisticsEngine()

    result = engine.calculate(
        [
            trade(100),
            trade(-150),
            trade(50),
        ]
    )

    assert result.max_drawdown >= 0


def test_sharpe_ratio():

    engine = StatisticsEngine()

    result = engine.calculate(
        [
            trade(20),
            trade(10),
            trade(15),
            trade(-5),
            trade(30),
        ]
    )

    assert isinstance(result.sharpe_ratio, float)


def test_result_types():

    engine = StatisticsEngine()

    result = engine.calculate(
        [
            trade(100),
        ]
    )

    assert isinstance(result.total_trades, int)

    assert isinstance(result.wins, int)

    assert isinstance(result.losses, int)

    assert isinstance(result.win_rate, float)

    assert isinstance(result.gross_profit, float)

    assert isinstance(result.gross_loss, float)

    assert isinstance(result.net_profit, float)

    assert isinstance(result.average_win, float)

    assert isinstance(result.average_loss, float)

    assert isinstance(result.profit_factor, float)

    assert isinstance(result.expectancy, float)

    assert isinstance(result.max_drawdown, float)

    assert isinstance(result.sharpe_ratio, float)