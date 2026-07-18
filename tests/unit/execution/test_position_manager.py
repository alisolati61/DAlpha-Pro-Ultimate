from datetime import UTC, datetime

import pytest

from src.execution.position_manager import (
    Position,
    PositionManager,
)


def create_position(
    symbol: str = "BTC/USDT",
    side: str = "BUY",
    size: float = 1.0,
    entry_price: float = 50_000.0,
) -> Position:

    return Position(
        symbol=symbol,
        side=side,
        size=size,
        entry_price=entry_price,
    )


@pytest.fixture
def manager():

    return PositionManager()


def test_open_position(
    manager,
):

    position = create_position()

    manager.open_position(position)

    assert manager.exists(
        "BTC/USDT"
    ) is True

    assert manager.count() == 1


def test_get_position(
    manager,
):

    manager.open_position(
        create_position()
    )

    position = manager.get_position(
        "BTC/USDT"
    )

    assert position is not None

    assert position.symbol == "BTC/USDT"

    assert position.side == "BUY"

    assert position.size == 1.0

    assert position.entry_price == 50_000.0


def test_close_position(
    manager,
):

    manager.open_position(
        create_position()
    )

    closed = manager.close_position(
        "BTC/USDT"
    )

    assert closed.symbol == "BTC/USDT"

    assert manager.exists(
        "BTC/USDT"
    ) is False

    assert manager.count() == 0


def test_unknown_position_returns_none(
    manager,
):

    assert manager.get_position(
        "BTC/USDT"
    ) is None


def test_unknown_position_close_raises(
    manager,
):

    with pytest.raises(
        KeyError,
        match="Unknown position",
    ):

        manager.close_position(
            "BTC/USDT"
        )


def test_list_positions(
    manager,
):

    manager.open_position(
        create_position(
            "BTC/USDT"
        )
    )

    manager.open_position(
        create_position(
            "ETH/USDT"
        )
    )

    positions = manager.list_positions()

    assert len(positions) == 2

    assert {
        position.symbol
        for position in positions
    } == {
        "BTC/USDT",
        "ETH/USDT",
    }


def test_duplicate_position_is_rejected(
    manager,
):

    manager.open_position(
        create_position()
    )

    with pytest.raises(
        ValueError,
        match="already exists",
    ):

        manager.open_position(
            create_position()
        )


def test_buy_unrealized_pnl(
    manager,
):

    manager.open_position(
        create_position(
            side="BUY",
            size=2,
            entry_price=100,
        )
    )

    manager.update_price(
        "BTC/USDT",
        110,
    )

    position = manager.get_position(
        "BTC/USDT"
    )

    assert position is not None

    assert position.current_price == 110.0

    assert position.unrealized_pnl == 20.0


def test_sell_unrealized_pnl(
    manager,
):

    manager.open_position(
        create_position(
            side="SELL",
            size=2,
            entry_price=100,
        )
    )

    manager.update_price(
        "BTC/USDT",
        90,
    )

    position = manager.get_position(
        "BTC/USDT"
    )

    assert position is not None

    assert position.current_price == 90.0

    assert position.unrealized_pnl == 20.0


def test_buy_loss(
    manager,
):

    manager.open_position(
        create_position(
            side="BUY",
            size=2,
            entry_price=100,
        )
    )

    manager.update_price(
        "BTC/USDT",
        90,
    )

    position = manager.get_position(
        "BTC/USDT"
    )

    assert position is not None

    assert position.unrealized_pnl == -20.0


def test_sell_loss(
    manager,
):

    manager.open_position(
        create_position(
            side="SELL",
            size=2,
            entry_price=100,
        )
    )

    manager.update_price(
        "BTC/USDT",
        110,
    )

    position = manager.get_position(
        "BTC/USDT"
    )

    assert position is not None

    assert position.unrealized_pnl == -20.0


@pytest.mark.parametrize(
    "side, expected",
    [
        ("BUY", "BUY"),
        ("buy", "BUY"),
        (" Buy ", "BUY"),
        ("SELL", "SELL"),
        ("sell", "SELL"),
        (" Sell ", "SELL"),
    ],
)
def test_side_normalization(
    manager,
    side,
    expected,
):

    manager.open_position(
        create_position(
            side=side
        )
    )

    position = manager.get_position(
        "BTC/USDT"
    )

    assert position is not None

    assert position.side == expected


@pytest.mark.parametrize(
    "size",
    [
        0,
        -1,
        -0.5,
        float("nan"),
        float("inf"),
        float("-inf"),
    ],
)
def test_invalid_size(
    manager,
    size,
):

    with pytest.raises(
        ValueError,
    ):

        manager.open_position(
            create_position(
                size=size
            )
        )


@pytest.mark.parametrize(
    "entry_price",
    [
        0,
        -1,
        float("nan"),
        float("inf"),
        float("-inf"),
    ],
)
def test_invalid_entry_price(
    manager,
    entry_price,
):

    with pytest.raises(
        ValueError,
    ):

        manager.open_position(
            create_position(
                entry_price=entry_price
            )
        )


@pytest.mark.parametrize(
    "side",
    [
        "",
        "HOLD",
        "UNKNOWN",
    ],
)
def test_invalid_side(
    manager,
    side,
):

    with pytest.raises(
        ValueError,
    ):

        manager.open_position(
            create_position(
                side=side
            )
        )


def test_invalid_symbol(
    manager,
):

    with pytest.raises(
        ValueError,
    ):

        manager.open_position(
            create_position(
                symbol=" "
            )
        )


def test_invalid_symbol_type(
    manager,
):

    with pytest.raises(
        TypeError,
    ):

        manager.open_position(
            create_position(
                symbol=None
            )
        )


def test_invalid_position_type(
    manager,
):

    with pytest.raises(
        TypeError,
    ):

        manager.open_position(
            None
        )


def test_update_price(
    manager,
):

    manager.open_position(
        create_position()
    )

    manager.update_price(
        "BTC/USDT",
        51_000,
    )

    position = manager.get_position(
        "BTC/USDT"
    )

    assert position is not None

    assert position.current_price == 51_000.0


@pytest.mark.parametrize(
    "price",
    [
        0,
        -1,
        float("nan"),
        float("inf"),
        float("-inf"),
    ],
)
def test_invalid_update_price(
    manager,
    price,
):

    manager.open_position(
        create_position()
    )

    with pytest.raises(
        ValueError,
    ):

        manager.update_price(
            "BTC/USDT",
            price,
        )


def test_update_unknown_position(
    manager,
):

    with pytest.raises(
        KeyError,
        match="Unknown position",
    ):

        manager.update_price(
            "BTC/USDT",
            50_000,
        )


def test_get_returns_copy(
    manager,
):

    manager.open_position(
        create_position()
    )

    position = manager.get_position(
        "BTC/USDT"
    )

    assert position is not None

    position.size = 999

    stored = manager.get_position(
        "BTC/USDT"
    )

    assert stored is not None

    assert stored.size == 1.0


def test_list_returns_copies(
    manager,
):

    manager.open_position(
        create_position()
    )

    positions = manager.list_positions()

    positions[0].size = 999

    stored = manager.get_position(
        "BTC/USDT"
    )

    assert stored is not None

    assert stored.size == 1.0


def test_position_is_copied_on_open(
    manager,
):

    position = create_position()

    manager.open_position(
        position
    )

    position.size = 999

    stored = manager.get_position(
        "BTC/USDT"
    )

    assert stored is not None

    assert stored.size == 1.0


def test_leverage_must_be_positive(
    manager,
):

    with pytest.raises(
        ValueError,
    ):

        manager.open_position(
            Position(
                symbol="BTC/USDT",
                side="BUY",
                size=1,
                entry_price=100,
                leverage=0,
            )
        )


def test_stop_loss_is_validated(
    manager,
):

    with pytest.raises(
        ValueError,
    ):

        manager.open_position(
            Position(
                symbol="BTC/USDT",
                side="BUY",
                size=1,
                entry_price=100,
                stop_loss=0,
            )
        )


def test_take_profit_is_validated(
    manager,
):

    with pytest.raises(
        ValueError,
    ):

        manager.open_position(
            Position(
                symbol="BTC/USDT",
                side="BUY",
                size=1,
                entry_price=100,
                take_profit=-1,
            )
        )


def test_opened_at_must_be_timezone_aware(
    manager,
):

    with pytest.raises(
        ValueError,
    ):

        manager.open_position(
            Position(
                symbol="BTC/USDT",
                side="BUY",
                size=1,
                entry_price=100,
                opened_at=datetime.now(),
            )
        )


def test_default_opened_at_is_utc(
    manager,
):

    position = create_position()

    manager.open_position(
        position
    )

    stored = manager.get_position(
        "BTC/USDT"
    )

    assert stored is not None

    assert stored.opened_at.tzinfo == UTC


def test_current_price_defaults_to_none():

    position = create_position()

    assert position.current_price is None