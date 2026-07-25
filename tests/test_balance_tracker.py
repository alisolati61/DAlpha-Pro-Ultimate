"""Tests for thread-safe validated asset balance tracking."""

from concurrent.futures import ThreadPoolExecutor
from fractions import Fraction
from math import inf, nan

import pytest

from src.execution.balance_tracker import (
    AssetBalance,
    BalanceTracker,
)


@pytest.fixture
def tracker() -> BalanceTracker:
    return BalanceTracker()


def make_balance(
    asset: str = "BTC",
    free: float = 1.0,
    locked: float = 0.0,
) -> AssetBalance:
    return AssetBalance(
        asset=asset,
        free=free,
        locked=locked,
    )


def test_empty_tracker(
    tracker: BalanceTracker,
) -> None:
    assert tracker.count() == 0
    assert len(tracker) == 0
    assert bool(tracker) is False
    assert tracker.all_balances() == []
    assert tracker.snapshot() == ()
    assert tracker.total_balance() == 0.0
    assert tracker.total_free() == 0.0
    assert tracker.total_locked() == 0.0
    assert list(tracker) == []


def test_update_balance(
    tracker: BalanceTracker,
) -> None:
    result = tracker.update(
        asset="btc",
        free=1.5,
        locked=0.5,
    )

    balance = tracker.get("BTC")

    assert result is None
    assert isinstance(
        balance,
        AssetBalance,
    )
    assert balance.asset == "BTC"
    assert balance.free == 1.5
    assert balance.locked == 0.5
    assert balance.total == 2.0


def test_asset_is_normalized(
    tracker: BalanceTracker,
) -> None:
    tracker.update(
        asset="  btc  ",
        free=1,
        locked=0,
    )

    assert tracker.exists("BTC") is True
    assert tracker.exists(" btc ") is True

    balance = tracker.get("btc")

    assert balance is not None
    assert balance.asset == "BTC"


def test_update_replaces_existing_balance(
    tracker: BalanceTracker,
) -> None:
    tracker.update("BTC", 1, 2)
    tracker.update("btc", 10, 20)

    assert tracker.count() == 1

    balance = tracker.require("BTC")

    assert balance.free == 10.0
    assert balance.locked == 20.0


def test_zero_balances_are_allowed(
    tracker: BalanceTracker,
) -> None:
    tracker.update("BTC", 0, 0)

    balance = tracker.require("BTC")

    assert balance.total == 0.0
    assert balance.is_empty is True


def test_non_empty_balance_property() -> None:
    balance = make_balance(
        free=0,
        locked=1,
    )

    assert balance.is_empty is False


def test_direct_asset_balance_construction_remains_permissive() -> None:
    balance = AssetBalance(
        asset="raw",
        free=-1,
        locked=-2,
    )

    assert balance.total == -3.0


def test_fraction_amounts_are_supported(
    tracker: BalanceTracker,
) -> None:
    tracker.update(
        "BTC",
        Fraction(1, 2),
        Fraction(1, 4),
    )

    balance = tracker.require("BTC")

    assert balance.free == 0.5
    assert balance.locked == 0.25
    assert balance.total == 0.75


@pytest.mark.parametrize(
    "asset",
    [
        "",
        " ",
        "\t",
        "\n",
    ],
)
def test_empty_asset_is_rejected(
    tracker: BalanceTracker,
    asset: str,
) -> None:
    with pytest.raises(
        ValueError,
        match="asset cannot be empty",
    ):
        tracker.update(
            asset,
            1,
            0,
        )


@pytest.mark.parametrize(
    "asset",
    [
        None,
        123,
        True,
        [],
        {},
        object(),
    ],
)
def test_invalid_asset_type(
    tracker: BalanceTracker,
    asset: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="asset must be a string",
    ):
        tracker.update(
            asset,  # type: ignore[arg-type]
            1,
            0,
        )


def test_asset_length_is_bounded(
    tracker: BalanceTracker,
) -> None:
    with pytest.raises(
        ValueError,
        match=(
            "asset must not exceed "
            "100 characters"
        ),
    ):
        tracker.update(
            "x" * 101,
            1,
            0,
        )


def test_maximum_asset_length_is_accepted(
    tracker: BalanceTracker,
) -> None:
    tracker.update(
        "x" * 100,
        1,
        0,
    )

    assert tracker.count() == 1


@pytest.mark.parametrize(
    "field",
    [
        "free",
        "locked",
    ],
)
@pytest.mark.parametrize(
    "value",
    [
        -1,
        -0.1,
    ],
)
def test_negative_amount_is_rejected(
    tracker: BalanceTracker,
    field: str,
    value: float,
) -> None:
    arguments = {
        "asset": "BTC",
        "free": 0,
        "locked": 0,
    }
    arguments[field] = value

    with pytest.raises(
        ValueError,
        match=f"{field} cannot be negative",
    ):
        tracker.update(**arguments)


@pytest.mark.parametrize(
    "field",
    [
        "free",
        "locked",
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
def test_non_finite_amount_is_rejected(
    tracker: BalanceTracker,
    field: str,
    value: float,
) -> None:
    arguments = {
        "asset": "BTC",
        "free": 0,
        "locked": 0,
    }
    arguments[field] = value

    with pytest.raises(
        ValueError,
        match=f"{field} must be finite",
    ):
        tracker.update(**arguments)


@pytest.mark.parametrize(
    "field",
    [
        "free",
        "locked",
    ],
)
@pytest.mark.parametrize(
    "value",
    [
        True,
        False,
        "1",
        None,
        [],
        {},
        object(),
    ],
)
def test_invalid_amount_type(
    tracker: BalanceTracker,
    field: str,
    value: object,
) -> None:
    arguments: dict[str, object] = {
        "asset": "BTC",
        "free": 0,
        "locked": 0,
    }
    arguments[field] = value

    with pytest.raises(
        TypeError,
        match=f"{field} must be a number",
    ):
        tracker.update(
            **arguments,  # type: ignore[arg-type]
        )


def test_non_finite_per_asset_total_is_rejected(
    tracker: BalanceTracker,
) -> None:
    with pytest.raises(
        ValueError,
        match="balance total must be finite",
    ):
        tracker.update(
            "BTC",
            1e308,
            1e308,
        )


def test_missing_balance_returns_none(
    tracker: BalanceTracker,
) -> None:
    assert tracker.get("BTC") is None


def test_require_returns_balance(
    tracker: BalanceTracker,
) -> None:
    tracker.update("BTC", 1, 2)

    balance = tracker.require("btc")

    assert balance.asset == "BTC"


def test_require_missing_balance_raises(
    tracker: BalanceTracker,
) -> None:
    with pytest.raises(
        KeyError,
        match="Unknown asset: BTC",
    ):
        tracker.require("btc")


def test_get_returns_copy(
    tracker: BalanceTracker,
) -> None:
    tracker.update("BTC", 1, 2)

    balance = tracker.require("BTC")
    balance.free = 999

    stored = tracker.require("BTC")

    assert stored.free == 1.0


def test_all_balances_returns_copies(
    tracker: BalanceTracker,
) -> None:
    tracker.update("BTC", 1, 2)

    balances = tracker.all_balances()
    balances[0].free = 999
    balances.clear()

    stored = tracker.require("BTC")

    assert stored.free == 1.0
    assert tracker.count() == 1


def test_all_balances_preserves_insertion_order(
    tracker: BalanceTracker,
) -> None:
    tracker.update("BTC", 1, 0)
    tracker.update("ETH", 2, 0)
    tracker.update("USDT", 3, 0)

    assert [
        balance.asset
        for balance in tracker.all_balances()
    ] == [
        "BTC",
        "ETH",
        "USDT",
    ]


def test_snapshot_is_independent_tuple(
    tracker: BalanceTracker,
) -> None:
    tracker.update("BTC", 1, 0)

    snapshot = tracker.snapshot()
    snapshot[0].free = 999

    assert type(snapshot) is tuple
    assert tracker.require("BTC").free == 1.0


def test_iterator_uses_snapshot(
    tracker: BalanceTracker,
) -> None:
    tracker.update("BTC", 1, 0)
    tracker.update("ETH", 2, 0)

    iterator = iter(tracker)
    tracker.clear()

    assert [
        balance.asset
        for balance in iterator
    ] == [
        "BTC",
        "ETH",
    ]


def test_total_balance_multiple_assets(
    tracker: BalanceTracker,
) -> None:
    tracker.update("BTC", 1, 2)
    tracker.update("USDT", 100, 50)

    assert tracker.total_balance() == 153.0
    assert tracker.total_free() == 101.0
    assert tracker.total_locked() == 52.0


def test_total_methods_return_exact_float(
    tracker: BalanceTracker,
) -> None:
    tracker.update("BTC", 1, 2)

    assert type(tracker.total_balance()) is float
    assert type(tracker.total_free()) is float
    assert type(tracker.total_locked()) is float


def test_asset_balance_total_is_float() -> None:
    balance = AssetBalance(
        asset="BTC",
        free=1,
        locked=2,
    )

    assert type(balance.total) is float


def test_remove_balance(
    tracker: BalanceTracker,
) -> None:
    tracker.update("BTC", 1, 2)

    removed = tracker.remove(" btc ")

    assert removed == AssetBalance(
        asset="BTC",
        free=1.0,
        locked=2.0,
    )
    assert tracker.exists("BTC") is False


def test_remove_returns_defensive_copy(
    tracker: BalanceTracker,
) -> None:
    tracker.update("BTC", 1, 2)

    removed = tracker.remove("BTC")
    removed.free = 999

    assert tracker.count() == 0


def test_remove_missing_balance_raises(
    tracker: BalanceTracker,
) -> None:
    with pytest.raises(
        KeyError,
        match="Unknown asset: BTC",
    ):
        tracker.remove("BTC")


def test_update_many(
    tracker: BalanceTracker,
) -> None:
    balances = [
        make_balance("btc", 1, 2),
        make_balance("eth", 3, 4),
    ]

    count = tracker.update_many(balances)

    assert count == 2
    assert [
        balance.asset
        for balance in tracker.all_balances()
    ] == [
        "BTC",
        "ETH",
    ]


def test_update_many_accepts_generator(
    tracker: BalanceTracker,
) -> None:
    count = tracker.update_many(
        make_balance(
            asset=f"asset-{index}",
            free=index,
        )
        for index in range(3)
    )

    assert count == 3
    assert tracker.count() == 3


def test_update_many_empty_iterable(
    tracker: BalanceTracker,
) -> None:
    assert tracker.update_many([]) == 0
    assert tracker.count() == 0


@pytest.mark.parametrize(
    "balances",
    [
        None,
        1,
        True,
        object(),
        "balances",
        b"balances",
        bytearray(b"balances"),
    ],
)
def test_update_many_rejects_invalid_container(
    tracker: BalanceTracker,
    balances: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="balances must be an iterable",
    ):
        tracker.update_many(
            balances,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "balance",
    [
        None,
        1,
        True,
        "BTC",
        {},
        object(),
    ],
)
def test_update_many_rejects_invalid_item(
    tracker: BalanceTracker,
    balance: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="balance must be an AssetBalance",
    ):
        tracker.update_many(
            [
                balance,  # type: ignore[list-item]
            ]
        )


def test_update_many_rejects_normalized_duplicates(
    tracker: BalanceTracker,
) -> None:
    with pytest.raises(
        ValueError,
        match="Duplicate asset in balances",
    ):
        tracker.update_many(
            [
                make_balance("btc"),
                make_balance(" BTC "),
            ]
        )


def test_update_many_is_atomic_on_invalid_item(
    tracker: BalanceTracker,
) -> None:
    tracker.update("ORIGINAL", 1, 0)

    with pytest.raises(TypeError):
        tracker.update_many(
            [
                make_balance("BTC"),
                object(),  # type: ignore[list-item]
            ]
        )

    assert [
        balance.asset
        for balance in tracker.all_balances()
    ] == ["ORIGINAL"]


def test_update_many_stores_defensive_copies(
    tracker: BalanceTracker,
) -> None:
    source = make_balance("BTC", 1, 2)

    tracker.update_many([source])
    source.free = 999

    assert tracker.require("BTC").free == 1.0


def test_replace_all(
    tracker: BalanceTracker,
) -> None:
    tracker.update("OLD", 1, 0)

    count = tracker.replace_all(
        [
            make_balance("BTC", 1, 0),
            make_balance("ETH", 2, 0),
        ]
    )

    assert count == 2
    assert tracker.exists("OLD") is False
    assert [
        balance.asset
        for balance in tracker.all_balances()
    ] == [
        "BTC",
        "ETH",
    ]


def test_replace_all_with_empty_iterable_clears(
    tracker: BalanceTracker,
) -> None:
    tracker.update("BTC", 1, 0)

    assert tracker.replace_all([]) == 0
    assert tracker.count() == 0


def test_replace_all_is_atomic_on_invalid_input(
    tracker: BalanceTracker,
) -> None:
    tracker.update("ORIGINAL", 1, 0)

    with pytest.raises(ValueError):
        tracker.replace_all(
            [
                make_balance("BTC"),
                make_balance(" btc "),
            ]
        )

    assert tracker.exists("ORIGINAL") is True
    assert tracker.count() == 1


def test_clear(
    tracker: BalanceTracker,
) -> None:
    tracker.update("BTC", 1, 0)
    tracker.update("USDT", 100, 0)

    result = tracker.clear()

    assert result is None
    assert tracker.count() == 0
    assert tracker.total_balance() == 0.0
    assert tracker.all_balances() == []


def test_concurrent_updates_are_safe() -> None:
    tracker = BalanceTracker()

    def update(index: int) -> None:
        tracker.update(
            f"asset-{index}",
            index,
            index / 2,
        )

    with ThreadPoolExecutor(
        max_workers=16,
    ) as executor:
        list(
            executor.map(
                update,
                range(500),
            )
        )

    assert tracker.count() == 500
    assert len(
        {
            balance.asset
            for balance in tracker.snapshot()
        }
    ) == 500