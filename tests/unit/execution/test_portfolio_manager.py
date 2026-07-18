from __future__ import annotations

import math

import pytest

from src.execution.portfolio_manager import (
    PortfolioManager,
)
from src.execution.position_manager import (
    Position,
)


def make_position(
    symbol: str = "BTCUSDT",
    side: str = "BUY",
    size: float = 1.0,
    entry_price: float = 100.0,
    current_price: float = 110.0,
    unrealized_pnl: float = 10.0,
) -> Position:

    return Position(
        symbol=symbol,
        side=side,
        size=size,
        entry_price=entry_price,
        current_price=current_price,
        unrealized_pnl=unrealized_pnl,
    )


def test_default_balance_is_zero():

    manager = PortfolioManager()

    assert manager.get_balance() == 0.0


def test_initial_balance_is_float():

    manager = PortfolioManager(
        balance=10_000,
    )

    assert isinstance(
        manager.get_balance(),
        float,
    )

    assert manager.get_balance() == 10_000.0


def test_negative_balance_is_rejected():

    with pytest.raises(
        ValueError,
        match="balance cannot be negative",
    ):

        PortfolioManager(
            balance=-1,
        )


@pytest.mark.parametrize(
    "invalid_balance",
    [
        None,
        "10000",
        [],
        {},
        object(),
    ],
)
def test_invalid_balance_type_is_rejected(
    invalid_balance,
):

    with pytest.raises(
        TypeError,
        match="balance must be a number",
    ):

        PortfolioManager(
            balance=invalid_balance,
        )


def test_bool_balance_is_rejected():

    with pytest.raises(
        TypeError,
        match="balance must be a number",
    ):

        PortfolioManager(
            balance=True,
        )


@pytest.mark.parametrize(
    "invalid_balance",
    [
        math.inf,
        -math.inf,
        math.nan,
    ],
)
def test_non_finite_balance_is_rejected(
    invalid_balance,
):

    with pytest.raises(
        ValueError,
        match="balance must be finite",
    ):

        PortfolioManager(
            balance=invalid_balance,
        )


def test_set_balance():

    manager = PortfolioManager()

    manager.set_balance(
        25_000,
    )

    assert manager.get_balance() == 25_000.0


def test_set_balance_rejects_negative_value():

    manager = PortfolioManager()

    with pytest.raises(
        ValueError,
        match="balance cannot be negative",
    ):

        manager.set_balance(
            -1,
        )


def test_positions_are_empty_initially():

    manager = PortfolioManager()

    assert manager.all_positions() == []


def test_add_position():

    manager = PortfolioManager()

    position = make_position()

    manager.add_position(
        position,
    )

    assert manager.get_position(
        "BTCUSDT",
    ) is position


def test_add_position_requires_position_instance():

    manager = PortfolioManager()

    with pytest.raises(
        TypeError,
        match="position must be a Position",
    ):

        manager.add_position(
            object(),
        )


def test_add_position_normalizes_symbol():

    manager = PortfolioManager()

    position = make_position(
        symbol="  BTCUSDT  ",
    )

    manager.add_position(
        position,
    )

    assert position.symbol == "BTCUSDT"

    assert manager.get_position(
        "BTCUSDT",
    ) is position


def test_add_position_replaces_same_symbol():

    manager = PortfolioManager()

    first = make_position(
        unrealized_pnl=10.0,
    )

    second = make_position(
        unrealized_pnl=20.0,
    )

    manager.add_position(
        first,
    )

    manager.add_position(
        second,
    )

    assert manager.get_position(
        "BTCUSDT",
    ) is second

    assert len(
        manager.all_positions(),
    ) == 1


def test_remove_position():

    manager = PortfolioManager()

    manager.add_position(
        make_position(),
    )

    manager.remove_position(
        "BTCUSDT",
    )

    assert manager.get_position(
        "BTCUSDT",
    ) is None


def test_remove_nonexistent_position_is_safe():

    manager = PortfolioManager()

    manager.remove_position(
        "BTCUSDT",
    )

    assert manager.all_positions() == []


def test_get_nonexistent_position_returns_none():

    manager = PortfolioManager()

    assert manager.get_position(
        "BTCUSDT",
    ) is None


@pytest.mark.parametrize(
    "invalid_symbol",
    [
        None,
        123,
        [],
        {},
        object(),
    ],
)
def test_get_position_rejects_invalid_symbol(
    invalid_symbol,
):

    manager = PortfolioManager()

    with pytest.raises(
        TypeError,
        match="symbol must be a string",
    ):

        manager.get_position(
            invalid_symbol,
        )


def test_empty_symbol_is_rejected():

    manager = PortfolioManager()

    with pytest.raises(
        ValueError,
        match="symbol cannot be empty",
    ):

        manager.get_position(
            "   ",
        )


def test_all_positions_returns_list():

    manager = PortfolioManager()

    position = make_position()

    manager.add_position(
        position,
    )

    positions = manager.all_positions()

    assert isinstance(
        positions,
        list,
    )

    assert positions == [
        position,
    ]


def test_all_positions_returns_copy():

    manager = PortfolioManager()

    position = make_position()

    manager.add_position(
        position,
    )

    positions = manager.all_positions()

    positions.clear()

    assert len(
        manager.all_positions(),
    ) == 1


def test_total_unrealized_pnl():

    manager = PortfolioManager()

    manager.add_position(
        make_position(
            symbol="BTCUSDT",
            unrealized_pnl=100.0,
        ),
    )

    manager.add_position(
        make_position(
            symbol="ETHUSDT",
            unrealized_pnl=-25.0,
        ),
    )

    assert manager.total_unrealized_pnl() == 75.0


def test_total_unrealized_pnl_is_float():

    manager = PortfolioManager()

    manager.add_position(
        make_position(
            unrealized_pnl=100,
        ),
    )

    assert isinstance(
        manager.total_unrealized_pnl(),
        float,
    )


def test_equity():

    manager = PortfolioManager(
        balance=10_000,
    )

    manager.add_position(
        make_position(
            unrealized_pnl=250.0,
        ),
    )

    assert manager.equity() == 10_250.0


def test_equity_with_loss():

    manager = PortfolioManager(
        balance=10_000,
    )

    manager.add_position(
        make_position(
            unrealized_pnl=-500.0,
        ),
    )

    assert manager.equity() == 9_500.0


def test_total_exposure():

    manager = PortfolioManager()

    manager.add_position(
        make_position(
            symbol="BTCUSDT",
            size=2.0,
            current_price=100.0,
        ),
    )

    manager.add_position(
        make_position(
            symbol="ETHUSDT",
            size=3.0,
            current_price=50.0,
        ),
    )

    assert manager.total_exposure() == 350.0


def test_total_exposure_uses_absolute_value():

    manager = PortfolioManager()

    manager.add_position(
        make_position(
            size=-2.0,
            current_price=100.0,
        ),
    )

    assert manager.total_exposure() == 200.0


def test_total_exposure_is_float():

    manager = PortfolioManager()

    manager.add_position(
        make_position(
            size=1,
            current_price=100,
        ),
    )

    assert isinstance(
        manager.total_exposure(),
        float,
    )


def test_remove_position_normalizes_symbol():

    manager = PortfolioManager()

    manager.add_position(
        make_position(),
    )

    manager.remove_position(
        "  BTCUSDT  ",
    )

    assert manager.get_position(
        "BTCUSDT",
    ) is None