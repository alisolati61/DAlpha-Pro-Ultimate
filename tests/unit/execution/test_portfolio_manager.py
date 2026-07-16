from src.execution.portfolio_manager import (
    PortfolioManager,
)
from src.execution.position_manager import (
    Position,
)


def test_balance():

    manager = PortfolioManager()

    manager.set_balance(10000)

    assert manager.get_balance() == 10000


def test_add_position():

    manager = PortfolioManager()

    manager.add_position(
        Position(
            symbol="BTCUSDT",
            side="BUY",
            size=1,
            entry_price=100000,
        )
    )

    assert manager.get_position(
        "BTCUSDT"
    ) is not None


def test_equity():

    manager = PortfolioManager()

    manager.set_balance(10000)

    position = Position(
        symbol="BTCUSDT",
        side="BUY",
        size=1,
        entry_price=100000,
    )

    position.unrealized_pnl = 500

    manager.add_position(position)

    assert manager.equity() == 10500


def test_remove_position():

    manager = PortfolioManager()

    manager.add_position(
        Position(
            symbol="BTCUSDT",
            side="BUY",
            size=1,
            entry_price=100000,
        )
    )

    manager.remove_position("BTCUSDT")

    assert manager.get_position("BTCUSDT") is None


def test_total_exposure():

    manager = PortfolioManager()

    position = Position(
        symbol="BTCUSDT",
        side="BUY",
        size=2,
        entry_price=100000,
    )

    position.current_price = 100000

    manager.add_position(position)

    assert manager.total_exposure() == 200000