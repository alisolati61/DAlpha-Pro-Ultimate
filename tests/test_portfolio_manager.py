"""Tests for execution portfolio accounting and compatibility."""

from concurrent.futures import ThreadPoolExecutor
from fractions import Fraction
from math import inf, nan

import pytest

from src.execution.portfolio_manager import (
    PortfolioManager,
)
from src.execution.position_manager import (
    Position,
)


def make_position(
    **overrides: object,
) -> Position:
    values: dict[str, object] = {
        "symbol": "BTCUSDT",
        "side": "BUY",
        "size": 1.0,
        "entry_price": 100.0,
        "current_price": 110.0,
        "unrealized_pnl": 10.0,
        "realized_pnl": 0.0,
        "leverage": 1.0,
    }
    values.update(overrides)

    return Position(
        **values,  # type: ignore[arg-type]
    )


@pytest.fixture
def manager() -> PortfolioManager:
    return PortfolioManager()


def test_default_state(
    manager: PortfolioManager,
) -> None:
    assert manager.get_balance() == 0.0
    assert manager.all_positions() == []
    assert manager.snapshot() == ()
    assert manager.count() == 0
    assert len(manager) == 0
    assert bool(manager) is False
    assert manager.total_unrealized_pnl() == 0.0
    assert manager.total_realized_pnl() == 0.0
    assert manager.equity() == 0.0
    assert manager.total_exposure() == 0.0
    assert manager.net_exposure() == 0.0
    assert manager.total_margin_used() == 0.0
    assert manager.available_balance() == 0.0


def test_initial_balance_is_normalized() -> None:
    manager = PortfolioManager(
        balance=10_000,
    )

    assert manager.get_balance() == 10_000.0
    assert type(manager.get_balance()) is float


def test_fraction_balance_is_supported() -> None:
    manager = PortfolioManager(
        balance=Fraction(3, 2),
    )

    assert manager.get_balance() == 1.5


@pytest.mark.parametrize(
    "balance",
    [
        -1,
        -0.1,
    ],
)
def test_negative_balance_rejected(
    balance: float,
) -> None:
    with pytest.raises(
        ValueError,
        match="balance cannot be negative",
    ):
        PortfolioManager(balance)


@pytest.mark.parametrize(
    "balance",
    [
        nan,
        inf,
        -inf,
    ],
)
def test_non_finite_balance_rejected(
    balance: float,
) -> None:
    with pytest.raises(
        ValueError,
        match="balance must be finite",
    ):
        PortfolioManager(balance)


@pytest.mark.parametrize(
    "balance",
    [
        True,
        False,
        None,
        "100",
        [],
        {},
        object(),
    ],
)
def test_invalid_balance_type_rejected(
    balance: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="balance must be a number",
    ):
        PortfolioManager(
            balance=balance,  # type: ignore[arg-type]
        )


def test_set_balance(
    manager: PortfolioManager,
) -> None:
    result = manager.set_balance(25_000)

    assert result is None
    assert manager.get_balance() == 25_000.0


def test_failed_set_balance_is_atomic(
    manager: PortfolioManager,
) -> None:
    manager.set_balance(100)

    with pytest.raises(ValueError):
        manager.set_balance(-1)

    assert manager.get_balance() == 100.0


def test_adjust_balance(
    manager: PortfolioManager,
) -> None:
    manager.set_balance(100)

    assert manager.adjust_balance(25) == 125.0
    assert manager.adjust_balance(-20) == 105.0


def test_adjust_balance_cannot_go_negative(
    manager: PortfolioManager,
) -> None:
    manager.set_balance(100)

    with pytest.raises(
        ValueError,
        match="balance cannot be negative",
    ):
        manager.adjust_balance(-101)

    assert manager.get_balance() == 100.0


def test_deposit_and_withdraw(
    manager: PortfolioManager,
) -> None:
    assert manager.deposit(100) == 100.0
    assert manager.withdraw(40) == 60.0


@pytest.mark.parametrize(
    "amount",
    [
        0,
        -1,
    ],
)
def test_deposit_requires_positive_amount(
    manager: PortfolioManager,
    amount: float,
) -> None:
    with pytest.raises(
        ValueError,
        match="deposit amount must be greater than zero",
    ):
        manager.deposit(amount)


@pytest.mark.parametrize(
    "amount",
    [
        0,
        -1,
    ],
)
def test_withdraw_requires_positive_amount(
    manager: PortfolioManager,
    amount: float,
) -> None:
    with pytest.raises(
        ValueError,
        match="withdrawal amount must be greater than zero",
    ):
        manager.withdraw(amount)


def test_add_position_preserves_identity(
    manager: PortfolioManager,
) -> None:
    position = make_position()

    result = manager.add_position(position)

    assert result is None
    assert manager.get_position("BTCUSDT") is position


def test_add_position_normalizes_shared_object(
    manager: PortfolioManager,
) -> None:
    position = make_position(
        symbol="  BTCUSDT  ",
    )

    manager.add_position(position)

    assert position.symbol == "BTCUSDT"
    assert manager.get_position("BTCUSDT") is position


def test_same_symbol_replaces_previous_identity(
    manager: PortfolioManager,
) -> None:
    first = make_position(
        unrealized_pnl=10,
    )
    second = make_position(
        unrealized_pnl=20,
    )

    manager.add_position(first)
    manager.add_position(second)

    assert manager.get_position("BTCUSDT") is second
    assert manager.count() == 1


@pytest.mark.parametrize(
    "position",
    [
        None,
        1,
        True,
        "position",
        [],
        {},
        object(),
    ],
)
def test_invalid_position_type(
    manager: PortfolioManager,
    position: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="position must be a Position",
    ):
        manager.add_position(
            position  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "symbol",
    [
        "",
        " ",
        "\t",
        "\n",
    ],
)
def test_empty_position_symbol(
    manager: PortfolioManager,
    symbol: str,
) -> None:
    with pytest.raises(
        ValueError,
        match="symbol cannot be empty",
    ):
        manager.add_position(
            make_position(
                symbol=symbol,
            )
        )


@pytest.mark.parametrize(
    "symbol",
    [
        None,
        1,
        True,
        [],
        object(),
    ],
)
def test_invalid_position_symbol_type(
    manager: PortfolioManager,
    symbol: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="symbol must be a string",
    ):
        manager.add_position(
            make_position(
                symbol=symbol,
            )
        )


def test_symbol_length_is_bounded(
    manager: PortfolioManager,
) -> None:
    with pytest.raises(
        ValueError,
        match="symbol must not exceed 100 characters",
    ):
        manager.add_position(
            make_position(
                symbol="x" * 101,
            )
        )


def test_remove_position_is_safe_when_missing(
    manager: PortfolioManager,
) -> None:
    assert manager.remove_position("BTCUSDT") is None


def test_remove_position_normalizes_symbol(
    manager: PortfolioManager,
) -> None:
    manager.add_position(make_position())

    manager.remove_position("  BTCUSDT  ")

    assert manager.get_position("BTCUSDT") is None


def test_pop_position(
    manager: PortfolioManager,
) -> None:
    position = make_position()
    manager.add_position(position)

    assert manager.pop_position("BTCUSDT") is position
    assert manager.count() == 0


def test_pop_unknown_position(
    manager: PortfolioManager,
) -> None:
    with pytest.raises(
        KeyError,
        match="Unknown position: BTCUSDT",
    ):
        manager.pop_position("BTCUSDT")


def test_get_unknown_returns_none(
    manager: PortfolioManager,
) -> None:
    assert manager.get_position("BTCUSDT") is None


def test_require_returns_shared_identity(
    manager: PortfolioManager,
) -> None:
    position = make_position()
    manager.add_position(position)

    assert manager.require_position("BTCUSDT") is position


def test_require_unknown_raises(
    manager: PortfolioManager,
) -> None:
    with pytest.raises(
        KeyError,
        match="Unknown position: BTCUSDT",
    ):
        manager.require_position("BTCUSDT")


def test_exists(
    manager: PortfolioManager,
) -> None:
    assert manager.exists("BTCUSDT") is False

    manager.add_position(make_position())

    assert manager.exists(" BTCUSDT ") is True


@pytest.mark.parametrize(
    "symbol",
    [
        "",
        " ",
        "\t",
        "\n",
    ],
)
def test_lookup_rejects_empty_symbol(
    manager: PortfolioManager,
    symbol: str,
) -> None:
    with pytest.raises(
        ValueError,
        match="symbol cannot be empty",
    ):
        manager.get_position(symbol)


@pytest.mark.parametrize(
    "symbol",
    [
        None,
        1,
        True,
        [],
        {},
        object(),
    ],
)
def test_lookup_rejects_invalid_symbol_type(
    manager: PortfolioManager,
    symbol: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="symbol must be a string",
    ):
        manager.get_position(
            symbol  # type: ignore[arg-type]
        )


def test_all_positions_returns_new_list_with_live_objects(
    manager: PortfolioManager,
) -> None:
    position = make_position()
    manager.add_position(position)

    positions = manager.all_positions()

    assert positions == [position]
    assert positions[0] is position

    positions.clear()

    assert manager.count() == 1


def test_live_object_mutation_is_visible(
    manager: PortfolioManager,
) -> None:
    position = make_position()
    manager.add_position(position)

    position.unrealized_pnl = 99

    assert manager.total_unrealized_pnl() == 99.0


def test_get_position_copy_is_isolated(
    manager: PortfolioManager,
) -> None:
    position = make_position()
    manager.add_position(position)

    copied = manager.get_position_copy(
        "BTCUSDT"
    )

    assert copied == position
    assert copied is not position

    copied.unrealized_pnl = 999

    assert position.unrealized_pnl == 10.0


def test_snapshot_is_isolated(
    manager: PortfolioManager,
) -> None:
    position = make_position()
    manager.add_position(position)

    snapshot = manager.snapshot()

    assert type(snapshot) is tuple
    assert snapshot == (position,)
    assert snapshot[0] is not position

    snapshot[0].size = 999

    assert position.size == 1.0


def test_iterator_uses_isolated_snapshot(
    manager: PortfolioManager,
) -> None:
    first = make_position(
        symbol="BTCUSDT",
    )
    second = make_position(
        symbol="ETHUSDT",
    )
    manager.add_positions(
        [
            first,
            second,
        ]
    )

    iterator = iter(manager)
    manager.clear_positions()

    iterated = list(iterator)

    assert iterated == [
        first,
        second,
    ]
    assert iterated[0] is not first


def test_add_positions(
    manager: PortfolioManager,
) -> None:
    first = make_position(
        symbol=" BTCUSDT ",
    )
    second = make_position(
        symbol=" ETHUSDT ",
    )

    count = manager.add_positions(
        [
            first,
            second,
        ]
    )

    assert count == 2
    assert first.symbol == "BTCUSDT"
    assert second.symbol == "ETHUSDT"
    assert manager.all_positions() == [
        first,
        second,
    ]


def test_add_positions_accepts_generator(
    manager: PortfolioManager,
) -> None:
    count = manager.add_positions(
        make_position(
            symbol=f"ASSET-{index}",
        )
        for index in range(3)
    )

    assert count == 3


def test_add_positions_empty_iterable(
    manager: PortfolioManager,
) -> None:
    assert manager.add_positions([]) == 0


@pytest.mark.parametrize(
    "positions",
    [
        None,
        1,
        True,
        object(),
        "positions",
        b"positions",
        bytearray(b"positions"),
    ],
)
def test_add_positions_invalid_container(
    manager: PortfolioManager,
    positions: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="positions must be an iterable",
    ):
        manager.add_positions(
            positions  # type: ignore[arg-type]
        )


def test_add_positions_rejects_normalized_duplicates(
    manager: PortfolioManager,
) -> None:
    first = make_position(
        symbol="BTCUSDT",
    )
    second = make_position(
        symbol=" BTCUSDT ",
    )

    with pytest.raises(
        ValueError,
        match="Duplicate symbol in positions",
    ):
        manager.add_positions(
            [
                first,
                second,
            ]
        )

    assert first.symbol == "BTCUSDT"
    assert second.symbol == " BTCUSDT "
    assert manager.count() == 0


def test_add_positions_is_atomic_on_invalid_item(
    manager: PortfolioManager,
) -> None:
    original = make_position(
        symbol="ORIGINAL",
    )
    manager.add_position(original)

    with pytest.raises(TypeError):
        manager.add_positions(
            [
                make_position(
                    symbol="VALID",
                ),
                object(),  # type: ignore[list-item]
            ]
        )

    assert manager.all_positions() == [
        original,
    ]


def test_replace_positions(
    manager: PortfolioManager,
) -> None:
    manager.add_position(
        make_position(
            symbol="OLD",
        )
    )
    first = make_position(
        symbol="BTCUSDT",
    )
    second = make_position(
        symbol="ETHUSDT",
    )

    count = manager.replace_positions(
        [
            first,
            second,
        ]
    )

    assert count == 2
    assert manager.exists("OLD") is False
    assert manager.all_positions() == [
        first,
        second,
    ]


def test_replace_positions_empty_clears(
    manager: PortfolioManager,
) -> None:
    manager.add_position(make_position())

    assert manager.replace_positions([]) == 0
    assert manager.count() == 0


def test_total_unrealized_pnl(
    manager: PortfolioManager,
) -> None:
    manager.add_positions(
        [
            make_position(
                symbol="BTCUSDT",
                unrealized_pnl=100,
            ),
            make_position(
                symbol="ETHUSDT",
                unrealized_pnl=-25,
            ),
        ]
    )

    assert manager.total_unrealized_pnl() == 75.0
    assert type(manager.total_unrealized_pnl()) is float


def test_total_realized_pnl(
    manager: PortfolioManager,
) -> None:
    manager.add_positions(
        [
            make_position(
                symbol="BTCUSDT",
                realized_pnl=20,
            ),
            make_position(
                symbol="ETHUSDT",
                realized_pnl=-5,
            ),
        ]
    )

    assert manager.total_realized_pnl() == 15.0


@pytest.mark.parametrize(
    "field",
    [
        "unrealized_pnl",
        "realized_pnl",
    ],
)
@pytest.mark.parametrize(
    "value",
    [
        nan,
        inf,
        -inf,
    ],
)
def test_non_finite_pnl_rejected_during_aggregation(
    manager: PortfolioManager,
    field: str,
    value: float,
) -> None:
    manager.add_position(
        make_position(
            **{
                field: value,
            }
        )
    )

    method = (
        manager.total_unrealized_pnl
        if field == "unrealized_pnl"
        else manager.total_realized_pnl
    )

    with pytest.raises(
        ValueError,
        match=f"{field} must be finite",
    ):
        method()


def test_equity_with_profit_and_loss(
    manager: PortfolioManager,
) -> None:
    manager.set_balance(10_000)
    manager.add_positions(
        [
            make_position(
                symbol="BTCUSDT",
                unrealized_pnl=250,
            ),
            make_position(
                symbol="ETHUSDT",
                unrealized_pnl=-500,
            ),
        ]
    )

    assert manager.equity() == 9_750.0


def test_total_exposure(
    manager: PortfolioManager,
) -> None:
    manager.add_positions(
        [
            make_position(
                symbol="BTCUSDT",
                size=2,
                current_price=100,
            ),
            make_position(
                symbol="ETHUSDT",
                size=3,
                current_price=50,
            ),
        ]
    )

    assert manager.total_exposure() == 350.0


def test_total_exposure_uses_absolute_size(
    manager: PortfolioManager,
) -> None:
    manager.add_position(
        make_position(
            size=-2,
            current_price=100,
        )
    )

    assert manager.total_exposure() == 200.0


def test_total_exposure_falls_back_to_entry_price(
    manager: PortfolioManager,
) -> None:
    manager.add_position(
        make_position(
            size=2,
            entry_price=100,
            current_price=None,
        )
    )

    assert manager.total_exposure() == 200.0


@pytest.mark.parametrize(
    "field",
    [
        "size",
        "current_price",
    ],
)
@pytest.mark.parametrize(
    "value",
    [
        nan,
        inf,
        -inf,
    ],
)
def test_invalid_exposure_values(
    manager: PortfolioManager,
    field: str,
    value: float,
) -> None:
    manager.add_position(
        make_position(
            **{
                field: value,
            }
        )
    )

    with pytest.raises(ValueError):
        manager.total_exposure()


def test_net_exposure(
    manager: PortfolioManager,
) -> None:
    manager.add_positions(
        [
            make_position(
                symbol="BTCUSDT",
                side="BUY",
                size=2,
                current_price=100,
            ),
            make_position(
                symbol="ETHUSDT",
                side="SELL",
                size=3,
                current_price=50,
            ),
        ]
    )

    assert manager.net_exposure() == 50.0


def test_net_exposure_normalizes_side(
    manager: PortfolioManager,
) -> None:
    manager.add_position(
        make_position(
            side=" sell ",
            size=2,
            current_price=100,
        )
    )

    assert manager.net_exposure() == -200.0


def test_total_margin_used(
    manager: PortfolioManager,
) -> None:
    manager.add_positions(
        [
            make_position(
                symbol="BTCUSDT",
                size=2,
                current_price=100,
                leverage=2,
            ),
            make_position(
                symbol="ETHUSDT",
                size=3,
                current_price=50,
                leverage=5,
            ),
        ]
    )

    assert manager.total_margin_used() == 130.0


def test_available_balance(
    manager: PortfolioManager,
) -> None:
    manager.set_balance(1_000)
    manager.add_position(
        make_position(
            size=2,
            current_price=100,
            leverage=2,
        )
    )

    assert manager.available_balance() == 900.0


def test_clear_positions_preserves_balance(
    manager: PortfolioManager,
) -> None:
    manager.set_balance(1_000)
    manager.add_position(make_position())

    result = manager.clear_positions()

    assert result is None
    assert manager.count() == 0
    assert manager.get_balance() == 1_000.0


def test_concurrent_additions_are_safe() -> None:
    manager = PortfolioManager()
    positions = [
        make_position(
            symbol=f"ASSET-{index}",
        )
        for index in range(500)
    ]

    with ThreadPoolExecutor(
        max_workers=16,
    ) as executor:
        list(
            executor.map(
                manager.add_position,
                positions,
            )
        )

    assert manager.count() == 500
    assert len(
        {
            position.symbol
            for position
            in manager.all_positions()
        }
    ) == 500