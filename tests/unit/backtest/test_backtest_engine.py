from src.backtesting.backtest_engine import (
    BacktestEngine,
    BacktestResult,
)


def test_backtest_engine_returns_result():

    engine = BacktestEngine()

    trades = [
        120,
        -50,
        90,
        40,
        -30,
        150,
        -70,
    ]

    result = engine.evaluate(
        trades
    )

    assert isinstance(
        result,
        BacktestResult,
    )


def test_backtest_engine_total_trades():

    engine = BacktestEngine()

    result = engine.evaluate(
        [
            120,
            -50,
            90,
            40,
            -30,
            150,
            -70,
        ]
    )

    assert result.total_trades == 7


def test_backtest_engine_wins():

    engine = BacktestEngine()

    result = engine.evaluate(
        [
            120,
            -50,
            90,
            40,
            -30,
            150,
            -70,
        ]
    )

    assert result.wins == 4


def test_backtest_engine_losses():

    engine = BacktestEngine()

    result = engine.evaluate(
        [
            120,
            -50,
            90,
            40,
            -30,
            150,
            -70,
        ]
    )

    assert result.losses == 3


def test_backtest_engine_win_rate():

    engine = BacktestEngine()

    result = engine.evaluate(
        [
            120,
            -50,
            90,
            40,
            -30,
            150,
            -70,
        ]
    )

    assert result.win_rate == 57.14


def test_empty_trades():

    engine = BacktestEngine()

    result = engine.evaluate([])

    assert result.total_trades == 0
    assert result.wins == 0
    assert result.losses == 0
    assert result.win_rate == 0.0