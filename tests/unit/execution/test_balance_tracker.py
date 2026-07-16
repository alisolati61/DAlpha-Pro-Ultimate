from src.execution.balance_tracker import (
    BalanceTracker,
)


def test_add_balance():

    tracker = BalanceTracker()

    tracker.update(

        "USDT",

        free=1000,

        locked=200,

    )

    assert tracker.exists("USDT")


def test_total():

    tracker = BalanceTracker()

    tracker.update(

        "USDT",

        free=1000,

        locked=200,

    )

    tracker.update(

        "BTC",

        free=1,

        locked=0,

    )

    assert tracker.total_balance() == 1201


def test_get():

    tracker = BalanceTracker()

    tracker.update(

        "USDT",

        free=1000,

        locked=200,

    )

    balance = tracker.get("USDT")

    assert balance.free == 1000

    assert balance.locked == 200

    assert balance.total == 1200