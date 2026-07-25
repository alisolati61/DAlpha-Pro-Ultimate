"""Tests for thread-safe validated position management."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta, timezone
from fractions import Fraction
from math import inf, nan

import pytest

from src.execution.position_manager import (
    Position,
    PositionManager,
)


OPENED_AT = datetime(
    2026,
    7,
    25,
    10,
    0,
    tzinfo=UTC,
)


def make_position(
    **overrides: object,
) -> Position:
    values: dict[str, object] = {
        "symbol": "BTC/USDT",
        "side": "BUY",
        "size": 1.0,
        "entry_price": 50_000.0,
        "current_price": None,
        "unrealized_pnl": 0.0,
        "realized_pnl": 0.0,
        "leverage": 1.0,
        "stop_loss": None,
        "take_profit": None,
        "opened_at": OPENED_AT,
    }
    values.update(overrides)

    return Position(
        **values,  # type: ignore[arg-type]
    )


@pytest.fixture
def manager() -> PositionManager:
    return PositionManager()


def test_empty_manager(
    manager: PositionManager,
) -> None:
    assert manager.count() == 0
    assert len(manager) == 0
    assert bool(manager) is False
    assert manager.list_positions() == []
    assert manager.snapshot() == ()
    assert manager.total_unrealized_pnl() == 0.0
    assert manager.total_realized_pnl() == 0.0
    assert manager.gross_exposure() == 0.0
    assert manager.net_exposure() == 0.0
    assert manager.total_margin_used() == 0.0
    assert list(manager) == []


def test_open_position(
    manager: PositionManager,
) -> None:
    position = make_position()

    result = manager.open_position(position)

    assert result is None
    assert manager.exists("BTC/USDT") is True
    assert manager.count() == 1
    assert bool(manager) is True


def test_position_is_normalized(
    manager: PositionManager,
) -> None:
    source_time = datetime(
        2026,
        7,
        25,
        13,
        30,
        tzinfo=timezone(
            timedelta(hours=3, minutes=30)
        ),
    )

    manager.open_position(
        make_position(
            symbol="  BTC/USDT  ",
            side=" buy ",
            size=1,
            entry_price=50_000,
            leverage=2,
            opened_at=source_time,
        )
    )

    stored = manager.require_position(
        "BTC/USDT"
    )

    assert stored.symbol == "BTC/USDT"
    assert stored.side == "BUY"
    assert stored.size == 1.0
    assert stored.entry_price == 50_000.0
    assert stored.leverage == 2.0
    assert stored.opened_at == OPENED_AT
    assert stored.opened_at.tzinfo is UTC


def test_fraction_numbers_are_supported(
    manager: PositionManager,
) -> None:
    manager.open_position(
        make_position(
            size=Fraction(1, 2),
            entry_price=Fraction(
                100,
                1,
            ),
            leverage=Fraction(2, 1),
        )
    )

    stored = manager.require_position(
        "BTC/USDT"
    )

    assert stored.size == 0.5
    assert stored.entry_price == 100.0
    assert stored.leverage == 2.0


def test_open_stores_defensive_copy(
    manager: PositionManager,
) -> None:
    source = make_position()

    manager.open_position(source)
    source.size = 999
    source.side = "SELL"

    stored = manager.require_position(
        "BTC/USDT"
    )

    assert stored.size == 1.0
    assert stored.side == "BUY"


def test_get_returns_defensive_copy(
    manager: PositionManager,
) -> None:
    manager.open_position(make_position())

    first = manager.require_position(
        "BTC/USDT"
    )
    first.size = 999

    second = manager.require_position(
        "BTC/USDT"
    )

    assert second.size == 1.0


def test_list_returns_defensive_copies(
    manager: PositionManager,
) -> None:
    manager.open_position(make_position())

    positions = manager.list_positions()
    positions[0].size = 999
    positions.clear()

    assert manager.count() == 1
    assert (
        manager.require_position(
            "BTC/USDT"
        ).size
        == 1.0
    )


def test_duplicate_position_is_rejected(
    manager: PositionManager,
) -> None:
    manager.open_position(make_position())

    with pytest.raises(
        ValueError,
        match="Position already exists",
    ):
        manager.open_position(
            make_position(
                side="SELL",
            )
        )

    assert manager.count() == 1


@pytest.mark.parametrize(
    "position",
    [
        None,
        1,
        True,
        "position",
        {},
        [],
        object(),
    ],
)
def test_invalid_position_type(
    manager: PositionManager,
    position: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="position must be a Position",
    ):
        manager.open_position(
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
def test_empty_symbol_rejected(
    manager: PositionManager,
    symbol: str,
) -> None:
    with pytest.raises(
        ValueError,
        match="symbol cannot be empty",
    ):
        manager.open_position(
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
def test_invalid_symbol_type(
    manager: PositionManager,
    symbol: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="symbol must be a string",
    ):
        manager.open_position(
            make_position(
                symbol=symbol,
            )
        )


def test_symbol_length_is_bounded(
    manager: PositionManager,
) -> None:
    with pytest.raises(
        ValueError,
        match=(
            "symbol must not exceed "
            "100 characters"
        ),
    ):
        manager.open_position(
            make_position(
                symbol="x" * 101,
            )
        )


@pytest.mark.parametrize(
    ("source", "expected"),
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
    manager: PositionManager,
    source: str,
    expected: str,
) -> None:
    manager.open_position(
        make_position(
            side=source,
        )
    )

    assert (
        manager.require_position(
            "BTC/USDT"
        ).side
        == expected
    )


@pytest.mark.parametrize(
    "side",
    [
        "",
        " ",
        "HOLD",
        "LONG",
        "SHORT",
        "UNKNOWN",
    ],
)
def test_invalid_side_value(
    manager: PositionManager,
    side: str,
) -> None:
    with pytest.raises(
        ValueError,
        match=(
            "side must be 'BUY' "
            "or 'SELL'"
        ),
    ):
        manager.open_position(
            make_position(
                side=side,
            )
        )


@pytest.mark.parametrize(
    "side",
    [
        None,
        1,
        True,
        [],
        object(),
    ],
)
def test_invalid_side_type(
    manager: PositionManager,
    side: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="side must be a string",
    ):
        manager.open_position(
            make_position(
                side=side,
            )
        )


@pytest.mark.parametrize(
    "field",
    [
        "size",
        "entry_price",
        "leverage",
        "current_price",
        "stop_loss",
        "take_profit",
    ],
)
@pytest.mark.parametrize(
    "value",
    [
        0,
        -1,
        -0.1,
    ],
)
def test_non_positive_values_rejected(
    manager: PositionManager,
    field: str,
    value: float,
) -> None:
    with pytest.raises(
        ValueError,
        match=(
            f"{field} must be greater "
            "than zero"
        ),
    ):
        manager.open_position(
            make_position(
                **{
                    field: value,
                }
            )
        )


@pytest.mark.parametrize(
    "field",
    [
        "size",
        "entry_price",
        "leverage",
        "current_price",
        "stop_loss",
        "take_profit",
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
def test_non_finite_positive_fields_rejected(
    manager: PositionManager,
    field: str,
    value: float,
) -> None:
    with pytest.raises(
        ValueError,
        match=f"{field} must be finite",
    ):
        manager.open_position(
            make_position(
                **{
                    field: value,
                }
            )
        )


@pytest.mark.parametrize(
    "field",
    [
        "size",
        "entry_price",
        "leverage",
        "current_price",
        "stop_loss",
        "take_profit",
    ],
)
@pytest.mark.parametrize(
    "value",
    [
        True,
        False,
        "1",
        [],
        object(),
    ],
)
def test_invalid_positive_field_types(
    manager: PositionManager,
    field: str,
    value: object,
) -> None:
    with pytest.raises(
        TypeError,
        match=f"{field} must be a number",
    ):
        manager.open_position(
            make_position(
                **{
                    field: value,
                }
            )
        )


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
def test_non_finite_pnl_rejected(
    manager: PositionManager,
    field: str,
    value: float,
) -> None:
    with pytest.raises(
        ValueError,
        match=f"{field} must be finite",
    ):
        manager.open_position(
            make_position(
                **{
                    field: value,
                }
            )
        )


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
        True,
        False,
        "1",
        None,
        object(),
    ],
)
def test_invalid_pnl_type_rejected(
    manager: PositionManager,
    field: str,
    value: object,
) -> None:
    with pytest.raises(
        TypeError,
        match=f"{field} must be a number",
    ):
        manager.open_position(
            make_position(
                **{
                    field: value,
                }
            )
        )


def test_negative_finite_pnl_is_allowed(
    manager: PositionManager,
) -> None:
    manager.open_position(
        make_position(
            unrealized_pnl=-10,
            realized_pnl=-5,
        )
    )

    stored = manager.require_position(
        "BTC/USDT"
    )

    assert stored.unrealized_pnl == -10.0
    assert stored.realized_pnl == -5.0


def test_naive_opened_at_rejected(
    manager: PositionManager,
) -> None:
    with pytest.raises(
        ValueError,
        match=(
            "opened_at must be "
            "timezone-aware"
        ),
    ):
        manager.open_position(
            make_position(
                opened_at=datetime(
                    2026,
                    7,
                    25,
                    10,
                    0,
                )
            )
        )


@pytest.mark.parametrize(
    "opened_at",
    [
        None,
        "2026-07-25",
        1,
        True,
        object(),
    ],
)
def test_invalid_opened_at_type(
    manager: PositionManager,
    opened_at: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="opened_at must be a datetime",
    ):
        manager.open_position(
            make_position(
                opened_at=opened_at,
            )
        )


def test_default_opened_at_is_utc() -> None:
    position = Position(
        symbol="BTC/USDT",
        side="BUY",
        size=1,
        entry_price=100,
    )

    assert position.opened_at.tzinfo == UTC


def test_current_price_defaults_to_none() -> None:
    assert make_position().current_price is None


def test_position_notional_overflow_rejected(
    manager: PositionManager,
) -> None:
    with pytest.raises(
        ValueError,
        match="position notional must be finite",
    ):
        manager.open_position(
            make_position(
                size=1e308,
                entry_price=1e308,
            )
        )


def test_get_unknown_returns_none(
    manager: PositionManager,
) -> None:
    assert (
        manager.get_position(
            "BTC/USDT"
        )
        is None
    )


def test_require_unknown_raises(
    manager: PositionManager,
) -> None:
    with pytest.raises(
        KeyError,
        match="Unknown position: BTC/USDT",
    ):
        manager.require_position(
            "BTC/USDT"
        )


def test_close_position(
    manager: PositionManager,
) -> None:
    source = make_position()
    manager.open_position(source)

    closed = manager.close_position(
        " BTC/USDT "
    )

    assert closed == source
    assert closed is not source
    assert manager.exists("BTC/USDT") is False
    assert manager.count() == 0


def test_close_unknown_raises(
    manager: PositionManager,
) -> None:
    with pytest.raises(
        KeyError,
        match="Unknown position: BTC/USDT",
    ):
        manager.close_position(
            "BTC/USDT"
        )


def test_list_preserves_insertion_order(
    manager: PositionManager,
) -> None:
    positions = [
        make_position(
            symbol="BTC/USDT",
        ),
        make_position(
            symbol="ETH/USDT",
        ),
        make_position(
            symbol="SOL/USDT",
        ),
    ]
    manager.open_many(positions)

    assert manager.list_positions() == positions


def test_snapshot_is_independent(
    manager: PositionManager,
) -> None:
    manager.open_position(make_position())

    snapshot = manager.snapshot()
    snapshot[0].size = 999

    assert type(snapshot) is tuple
    assert (
        manager.require_position(
            "BTC/USDT"
        ).size
        == 1.0
    )


def test_iterator_uses_snapshot(
    manager: PositionManager,
) -> None:
    first = make_position(
        symbol="BTC/USDT",
    )
    second = make_position(
        symbol="ETH/USDT",
    )
    manager.open_many(
        [
            first,
            second,
        ]
    )

    iterator = iter(manager)
    manager.clear()

    assert list(iterator) == [
        first,
        second,
    ]


def test_buy_unrealized_profit(
    manager: PositionManager,
) -> None:
    manager.open_position(
        make_position(
            side="BUY",
            size=2,
            entry_price=100,
        )
    )

    manager.update_price(
        "BTC/USDT",
        110,
    )

    stored = manager.require_position(
        "BTC/USDT"
    )

    assert stored.current_price == 110.0
    assert stored.unrealized_pnl == 20.0


def test_buy_unrealized_loss(
    manager: PositionManager,
) -> None:
    manager.open_position(
        make_position(
            side="BUY",
            size=2,
            entry_price=100,
        )
    )

    manager.update_price(
        "BTC/USDT",
        90,
    )

    assert (
        manager.require_position(
            "BTC/USDT"
        ).unrealized_pnl
        == -20.0
    )


def test_sell_unrealized_profit(
    manager: PositionManager,
) -> None:
    manager.open_position(
        make_position(
            side="SELL",
            size=2,
            entry_price=100,
        )
    )

    manager.update_price(
        "BTC/USDT",
        90,
    )

    assert (
        manager.require_position(
            "BTC/USDT"
        ).unrealized_pnl
        == 20.0
    )


def test_sell_unrealized_loss(
    manager: PositionManager,
) -> None:
    manager.open_position(
        make_position(
            side="SELL",
            size=2,
            entry_price=100,
        )
    )

    manager.update_price(
        "BTC/USDT",
        110,
    )

    assert (
        manager.require_position(
            "BTC/USDT"
        ).unrealized_pnl
        == -20.0
    )


def test_update_price_unknown_position(
    manager: PositionManager,
) -> None:
    with pytest.raises(
        KeyError,
        match="Unknown position",
    ):
        manager.update_price(
            "BTC/USDT",
            100,
        )


@pytest.mark.parametrize(
    "price",
    [
        0,
        -1,
        nan,
        inf,
        -inf,
    ],
)
def test_invalid_update_price(
    manager: PositionManager,
    price: float,
) -> None:
    manager.open_position(make_position())

    with pytest.raises(ValueError):
        manager.update_price(
            "BTC/USDT",
            price,
        )

    stored = manager.require_position(
        "BTC/USDT"
    )
    assert stored.current_price is None
    assert stored.unrealized_pnl == 0.0


@pytest.mark.parametrize(
    "price",
    [
        True,
        False,
        "100",
        None,
        object(),
    ],
)
def test_invalid_update_price_type(
    manager: PositionManager,
    price: object,
) -> None:
    manager.open_position(make_position())

    with pytest.raises(
        TypeError,
        match="price must be a number",
    ):
        manager.update_price(
            "BTC/USDT",
            price,  # type: ignore[arg-type]
        )


def test_update_price_overflow_is_atomic(
    manager: PositionManager,
) -> None:
    manager.open_position(
        make_position(
            size=1e308,
            entry_price=1,
        )
    )

    with pytest.raises(
        ValueError,
        match="unrealized_pnl must be finite",
    ):
        manager.update_price(
            "BTC/USDT",
            1e308,
        )

    stored = manager.require_position(
        "BTC/USDT"
    )
    assert stored.current_price is None
    assert stored.unrealized_pnl == 0.0


def test_open_many(
    manager: PositionManager,
) -> None:
    values = [
        make_position(
            symbol="BTC/USDT",
        ),
        make_position(
            symbol="ETH/USDT",
        ),
    ]

    assert manager.open_many(values) == 2
    assert manager.list_positions() == values


def test_open_many_accepts_generator(
    manager: PositionManager,
) -> None:
    count = manager.open_many(
        make_position(
            symbol=f"ASSET-{index}",
        )
        for index in range(3)
    )

    assert count == 3


def test_open_many_empty_iterable(
    manager: PositionManager,
) -> None:
    assert manager.open_many([]) == 0


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
def test_open_many_invalid_container(
    manager: PositionManager,
    positions: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="positions must be an iterable",
    ):
        manager.open_many(positions)


def test_open_many_rejects_duplicate_symbols(
    manager: PositionManager,
) -> None:
    with pytest.raises(
        ValueError,
        match="Duplicate symbol in positions",
    ):
        manager.open_many(
            [
                make_position(
                    symbol="BTC/USDT",
                ),
                make_position(
                    symbol=" BTC/USDT ",
                ),
            ]
        )

    assert manager.count() == 0


def test_open_many_is_atomic_on_invalid_item(
    manager: PositionManager,
) -> None:
    original = make_position(
        symbol="ORIGINAL",
    )
    manager.open_position(original)

    with pytest.raises(TypeError):
        manager.open_many(
            [
                make_position(
                    symbol="VALID",
                ),
                object(),
            ]
        )

    assert manager.list_positions() == [
        original,
    ]


def test_open_many_rejects_existing_atomically(
    manager: PositionManager,
) -> None:
    original = make_position(
        symbol="BTC/USDT",
    )
    manager.open_position(original)

    with pytest.raises(
        ValueError,
        match="Position already exists",
    ):
        manager.open_many(
            [
                make_position(
                    symbol="ETH/USDT",
                ),
                make_position(
                    symbol="BTC/USDT",
                ),
            ]
        )

    assert manager.list_positions() == [
        original,
    ]


def test_update_prices(
    manager: PositionManager,
) -> None:
    manager.open_many(
        [
            make_position(
                symbol="BTC/USDT",
                side="BUY",
                size=2,
                entry_price=100,
            ),
            make_position(
                symbol="ETH/USDT",
                side="SELL",
                size=3,
                entry_price=50,
            ),
        ]
    )

    count = manager.update_prices(
        {
            "BTC/USDT": 110,
            "ETH/USDT": 40,
        }
    )

    assert count == 2
    assert (
        manager.require_position(
            "BTC/USDT"
        ).unrealized_pnl
        == 20.0
    )
    assert (
        manager.require_position(
            "ETH/USDT"
        ).unrealized_pnl
        == 30.0
    )


def test_update_prices_is_atomic_when_missing(
    manager: PositionManager,
) -> None:
    manager.open_position(
        make_position(
            symbol="BTC/USDT",
            entry_price=100,
        )
    )

    with pytest.raises(
        KeyError,
        match="Unknown position: ETH/USDT",
    ):
        manager.update_prices(
            {
                "BTC/USDT": 110,
                "ETH/USDT": 100,
            }
        )

    assert (
        manager.require_position(
            "BTC/USDT"
        ).current_price
        is None
    )


@pytest.mark.parametrize(
    "prices",
    [
        None,
        1,
        True,
        [],
        "prices",
        object(),
    ],
)
def test_update_prices_requires_mapping(
    manager: PositionManager,
    prices: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="prices must be a mapping",
    ):
        manager.update_prices(
            prices  # type: ignore[arg-type]
        )


def test_positions_by_side(
    manager: PositionManager,
) -> None:
    buy = make_position(
        symbol="BTC/USDT",
        side="BUY",
    )
    sell = make_position(
        symbol="ETH/USDT",
        side="SELL",
    )
    manager.open_many(
        [
            buy,
            sell,
        ]
    )

    assert manager.positions_by_side(
        " buy "
    ) == [buy]
    assert manager.positions_by_side(
        "SELL"
    ) == [sell]


def test_risk_levels_update(
    manager: PositionManager,
) -> None:
    manager.open_position(make_position())

    manager.update_risk_levels(
        "BTC/USDT",
        stop_loss=45_000,
        take_profit=60_000,
    )

    stored = manager.require_position(
        "BTC/USDT"
    )

    assert stored.stop_loss == 45_000.0
    assert stored.take_profit == 60_000.0


def test_risk_levels_can_be_cleared(
    manager: PositionManager,
) -> None:
    manager.open_position(
        make_position(
            stop_loss=45_000,
            take_profit=60_000,
        )
    )

    manager.update_risk_levels(
        "BTC/USDT"
    )

    stored = manager.require_position(
        "BTC/USDT"
    )

    assert stored.stop_loss is None
    assert stored.take_profit is None


def test_position_properties() -> None:
    position = make_position(
        side="BUY",
        size=2,
        entry_price=100,
        current_price=110,
        leverage=2,
    )

    assert position.mark_price == 110.0
    assert position.notional_value == 220.0
    assert position.signed_notional == 220.0
    assert position.margin_used == 110.0


def test_sell_signed_notional() -> None:
    position = make_position(
        side="SELL",
        size=2,
        entry_price=100,
    )

    assert position.mark_price == 100.0
    assert position.notional_value == 200.0
    assert position.signed_notional == -200.0


def test_aggregate_values(
    manager: PositionManager,
) -> None:
    manager.open_many(
        [
            make_position(
                symbol="BTC/USDT",
                side="BUY",
                size=2,
                entry_price=100,
                current_price=110,
                unrealized_pnl=20,
                realized_pnl=5,
                leverage=2,
            ),
            make_position(
                symbol="ETH/USDT",
                side="SELL",
                size=3,
                entry_price=50,
                current_price=40,
                unrealized_pnl=30,
                realized_pnl=-2,
                leverage=4,
            ),
        ]
    )

    assert manager.total_unrealized_pnl() == 50.0
    assert manager.total_realized_pnl() == 3.0
    assert manager.gross_exposure() == 340.0
    assert manager.net_exposure() == 100.0
    assert manager.total_margin_used() == 140.0


def test_clear(
    manager: PositionManager,
) -> None:
    manager.open_position(make_position())

    result = manager.clear()

    assert result is None
    assert manager.count() == 0


def test_concurrent_opens_are_safe() -> None:
    manager = PositionManager()
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
                manager.open_position,
                positions,
            )
        )

    assert manager.count() == 500
    assert len(
        {
            position.symbol
            for position in manager.snapshot()
        }
    ) == 500