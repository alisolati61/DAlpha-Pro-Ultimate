from src.backtesting.strategy_runner import (
    CandleSignal,
    StrategyRunner,
)


def make_signal(
    entry: float,
    exit: float,
):

    return CandleSignal(
        strategy="SMC",
        symbol="BTCUSDT",
        timeframe="1h",
        entry_price=entry,
        exit_price=exit,
        quantity=1.0,
        confidence=80.0,
        duration_minutes=60,
        risk_reward=2.0,
    )


def test_empty_runner():

    runner = StrategyRunner()

    result = runner.run([])

    assert result == []


def test_single_profitable_trade():

    runner = StrategyRunner()

    result = runner.run(
        [
            make_signal(
                100,
                120,
            )
        ]
    )

    assert len(result) == 1

    assert result[0].win is True

    assert result[0].pnl > 0


def test_single_losing_trade():

    runner = StrategyRunner()

    result = runner.run(
        [
            make_signal(
                120,
                100,
            )
        ]
    )

    assert len(result) == 1

    assert result[0].win is False

    assert result[0].pnl < 0


def test_multiple_signals():

    runner = StrategyRunner()

    result = runner.run(

        [

            make_signal(
                100,
                120,
            ),

            make_signal(
                150,
                120,
            ),

            make_signal(
                80,
                100,
            ),

        ]

    )

    assert len(result) == 3


def test_trade_information():

    runner = StrategyRunner()

    trade = runner.run(
        [
            make_signal(
                100,
                120,
            )
        ]
    )[0]

    assert trade.strategy == "SMC"

    assert trade.symbol == "BTCUSDT"

    assert trade.timeframe == "1h"

    assert trade.confidence == 80.0

    assert trade.duration_minutes == 60


def test_runner_result_types():

    runner = StrategyRunner()

    trade = runner.run(
        [
            make_signal(
                100,
                120,
            )
        ]
    )[0]

    assert isinstance(trade.pnl, float)

    assert isinstance(trade.win, bool)

    assert isinstance(trade.confidence, float)

    assert isinstance(trade.risk_reward, float)