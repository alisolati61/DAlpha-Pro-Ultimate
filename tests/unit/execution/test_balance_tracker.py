import pytest

from src.execution.balance_tracker import (
    AssetBalance,
    BalanceTracker,
)


@pytest.fixture
def tracker():

    return BalanceTracker()


def test_update_balance(
    tracker,
):

    tracker.update(
        asset="btc",
        free=1.5,
        locked=0.5,
    )

    balance = tracker.get(
        "BTC"
    )

    assert isinstance(
        balance,
        AssetBalance,
    )

    assert balance.asset == "BTC"

    assert balance.free == 1.5

    assert balance.locked == 0.5


def test_asset_is_normalized(
    tracker,
):

    tracker.update(
        asset="  btc  ",
        free=1,
        locked=0,
    )

    assert tracker.exists(
        "BTC"
    )

    balance = tracker.get(
        "btc"
    )

    assert balance is not None

    assert balance.asset == "BTC"


def test_total_balance(
    tracker,
):

    tracker.update(
        "BTC",
        1,
        2,
    )

    balance = tracker.get(
        "BTC"
    )

    assert balance is not None

    assert balance.total == 3.0


def test_total_balance_multiple_assets(
    tracker,
):

    tracker.update(
        "BTC",
        1,
        2,
    )

    tracker.update(
        "USDT",
        100,
        50,
    )

    assert tracker.total_balance() == 153.0


def test_missing_balance_returns_none(
    tracker,
):

    assert tracker.get(
        "BTC"
    ) is None


def test_exists(
    tracker,
):

    assert tracker.exists(
        "BTC"
    ) is False

    tracker.update(
        "BTC",
        1,
        0,
    )

    assert tracker.exists(
        "BTC"
    ) is True


def test_update_replaces_existing_balance(
    tracker,
):

    tracker.update(
        "BTC",
        1,
        2,
    )

    tracker.update(
        "BTC",
        10,
        20,
    )

    balance = tracker.get(
        "BTC"
    )

    assert balance is not None

    assert balance.free == 10.0

    assert balance.locked == 20.0


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
    tracker,
    asset,
):

    with pytest.raises(
        ValueError,
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
        [],
    ],
)
def test_invalid_asset_type(
    tracker,
    asset,
):

    with pytest.raises(
        TypeError,
    ):

        tracker.update(
            asset,
            1,
            0,
        )


@pytest.mark.parametrize(
    "free",
    [
        -1,
        -0.1,
    ],
)
def test_negative_free_is_rejected(
    tracker,
    free,
):

    with pytest.raises(
        ValueError,
    ):

        tracker.update(
            "BTC",
            free,
            0,
        )


@pytest.mark.parametrize(
    "locked",
    [
        -1,
        -0.1,
    ],
)
def test_negative_locked_is_rejected(
    tracker,
    locked,
):

    with pytest.raises(
        ValueError,
    ):

        tracker.update(
            "BTC",
            0,
            locked,
        )


@pytest.mark.parametrize(
    "value",
    [
        float("nan"),
        float("inf"),
        float("-inf"),
    ],
)
def test_non_finite_free_is_rejected(
    tracker,
    value,
):

    with pytest.raises(
        ValueError,
    ):

        tracker.update(
            "BTC",
            value,
            0,
        )


@pytest.mark.parametrize(
    "value",
    [
        float("nan"),
        float("inf"),
        float("-inf"),
    ],
)
def test_non_finite_locked_is_rejected(
    tracker,
    value,
):

    with pytest.raises(
        ValueError,
    ):

        tracker.update(
            "BTC",
            0,
            value,
        )


@pytest.mark.parametrize(
    "value",
    [
        "1",
        None,
        [],
    ],
)
def test_invalid_free_type(
    tracker,
    value,
):

    with pytest.raises(
        TypeError,
    ):

        tracker.update(
            "BTC",
            value,
            0,
        )


@pytest.mark.parametrize(
    "value",
    [
        "1",
        None,
        [],
    ],
)
def test_invalid_locked_type(
    tracker,
    value,
):

    with pytest.raises(
        TypeError,
    ):

        tracker.update(
            "BTC",
            0,
            value,
        )


def test_boolean_free_is_rejected(
    tracker,
):

    with pytest.raises(
        TypeError,
    ):

        tracker.update(
            "BTC",
            True,
            0,
        )


def test_boolean_locked_is_rejected(
    tracker,
):

    with pytest.raises(
        TypeError,
    ):

        tracker.update(
            "BTC",
            0,
            True,
        )


def test_get_returns_copy(
    tracker,
):

    tracker.update(
        "BTC",
        1,
        2,
    )

    balance = tracker.get(
        "BTC"
    )

    assert balance is not None

    balance.free = 999

    stored = tracker.get(
        "BTC"
    )

    assert stored is not None

    assert stored.free == 1.0


def test_all_balances_returns_copies(
    tracker,
):

    tracker.update(
        "BTC",
        1,
        2,
    )

    balances = tracker.all_balances()

    balances[0].free = 999

    stored = tracker.get(
        "BTC"
    )

    assert stored is not None

    assert stored.free == 1.0


def test_all_balances(
    tracker,
):

    tracker.update(
        "BTC",
        1,
        2,
    )

    tracker.update(
        "ETH",
        3,
        4,
    )

    balances = tracker.all_balances()

    assert len(
        balances
    ) == 2

    assert {
        balance.asset
        for balance
        in balances
    } == {
        "BTC",
        "ETH",
    }


def test_count(
    tracker,
):

    assert tracker.count() == 0

    tracker.update(
        "BTC",
        1,
        0,
    )

    tracker.update(
        "USDT",
        100,
        0,
    )

    assert tracker.count() == 2


def test_clear(
    tracker,
):

    tracker.update(
        "BTC",
        1,
        0,
    )

    tracker.update(
        "USDT",
        100,
        0,
    )

    tracker.clear()

    assert tracker.count() == 0

    assert tracker.total_balance() == 0

    assert tracker.all_balances() == []


def test_zero_balances_are_allowed(
    tracker,
):

    tracker.update(
        "BTC",
        0,
        0,
    )

    balance = tracker.get(
        "BTC"
    )

    assert balance is not None

    assert balance.total == 0.0


def test_total_balance_is_float(
    tracker,
):

    tracker.update(
        "BTC",
        1,
        2,
    )

    assert isinstance(
        tracker.total_balance(),
        float,
    )


def test_asset_balance_total_is_float():

    balance = AssetBalance(
        asset="BTC",
        free=1,
        locked=2,
    )

    assert isinstance(
        balance.total,
        float,
    )