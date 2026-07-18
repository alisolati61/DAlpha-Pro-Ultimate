from src.backtesting.trade_simulator import (
    TradeRequest,
    TradeSimulationResult,
    TradeSimulator,
)


def test_profitable_trade():

    simulator = TradeSimulator()

    result = simulator.simulate(
        TradeRequest(
            entry_price=100,
            exit_price=120,
            quantity=1,
        )
    )

    assert isinstance(result, TradeSimulationResult)

    assert result.gross_profit > 0

    assert result.net_profit > 0


def test_losing_trade():

    simulator = TradeSimulator()

    result = simulator.simulate(
        TradeRequest(
            entry_price=120,
            exit_price=100,
            quantity=1,
        )
    )

    assert result.gross_profit < 0

    assert result.net_profit < 0


def test_commission_is_applied():

    simulator = TradeSimulator()

    result = simulator.simulate(
        TradeRequest(
            entry_price=100,
            exit_price=110,
            quantity=2,
            commission=0.001,
            slippage=0,
        )
    )

    assert result.commission_paid > 0


def test_slippage_is_applied():

    simulator = TradeSimulator()

    result = simulator.simulate(
        TradeRequest(
            entry_price=100,
            exit_price=110,
            quantity=2,
            commission=0,
            slippage=0.001,
        )
    )

    assert result.slippage_cost > 0


def test_zero_quantity():

    simulator = TradeSimulator()

    result = simulator.simulate(
        TradeRequest(
            entry_price=100,
            exit_price=120,
            quantity=0,
        )
    )

    assert result.gross_profit == 0

    assert result.net_profit == 0

    assert result.return_percent == 0


def test_return_percent():

    simulator = TradeSimulator()

    result = simulator.simulate(
        TradeRequest(
            entry_price=100,
            exit_price=120,
            quantity=1,
        )
    )

    assert result.return_percent > 0


def test_result_types():

    simulator = TradeSimulator()

    result = simulator.simulate(
        TradeRequest(
            entry_price=100,
            exit_price=120,
            quantity=1,
        )
    )

    assert isinstance(result.gross_profit, float)

    assert isinstance(result.commission_paid, float)

    assert isinstance(result.slippage_cost, float)

    assert isinstance(result.net_profit, float)

    assert isinstance(result.return_percent, float)