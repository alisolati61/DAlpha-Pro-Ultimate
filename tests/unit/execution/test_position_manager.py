from src.execution.position_manager import (
    Position,
    PositionManager,
)


def test_open_position():

    manager = PositionManager()

    manager.open_position(
        Position(
            symbol="BTCUSDT",
            side="BUY",
            size=1,
            entry_price=100000,
        )
    )

    assert manager.exists("BTCUSDT")


def test_get_position():

    manager = PositionManager()

    manager.open_position(
        Position(
            symbol="BTCUSDT",
            side="BUY",
            size=2,
            entry_price=100000,
        )
    )

    position = manager.get_position("BTCUSDT")

    assert position is not None
    assert position.symbol == "BTCUSDT"
    assert position.size == 2


def test_update_price_buy():

    manager = PositionManager()

    manager.open_position(
        Position(
            symbol="BTCUSDT",
            side="BUY",
            size=1,
            entry_price=100000,
        )
    )

    manager.update_price(
        "BTCUSDT",
        101000,
    )

    position = manager.get_position("BTCUSDT")

    assert position is not None
    assert position.current_price == 101000
    assert position.unrealized_pnl == 1000


def test_update_price_sell():

    manager = PositionManager()

    manager.open_position(
        Position(
            symbol="BTCUSDT",
            side="SELL",
            size=1,
            entry_price=100000,
        )
    )

    manager.update_price(
        "BTCUSDT",
        99000,
    )

    position = manager.get_position("BTCUSDT")

    assert position is not None
    assert position.unrealized_pnl == 1000


def test_close_position():

    manager = PositionManager()

    manager.open_position(
        Position(
            symbol="BTCUSDT",
            side="BUY",
            size=1,
            entry_price=100000,
        )
    )

    manager.close_position("BTCUSDT")

    assert not manager.exists("BTCUSDT")


def test_list_positions():

    manager = PositionManager()

    manager.open_position(
        Position(
            symbol="BTCUSDT",
            side="BUY",
            size=1,
            entry_price=100000,
        )
    )

    manager.open_position(
        Position(
            symbol="ETHUSDT",
            side="SELL",
            size=2,
            entry_price=3000,
        )
    )

    positions = manager.list_positions()

    assert len(positions) == 2