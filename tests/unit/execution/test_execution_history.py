from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.execution.execution_history import (
    ExecutionHistory,
)
from src.execution.execution_report import (
    ExecutionReport,
)


def make_report(
    order_id: str = "order-1",
    symbol: str = "BTCUSDT",
    success: bool = True,
    quantity: float = 1.0,
    price: float = 100.0,
    message: str = "Order executed.",
) -> ExecutionReport:

    return ExecutionReport(
        order_id=order_id,
        symbol=symbol,
        success=success,
        quantity=quantity,
        executed_price=price,
        message=message,
        timestamp=datetime.now(UTC),
    )


def test_default_max_size_is_1000():

    history = ExecutionHistory()

    assert history.max_size == 1000


@pytest.mark.parametrize(
    "max_size",
    [
        0,
        -1,
        -100,
    ],
)
def test_invalid_max_size_rejected(
    max_size,
):

    with pytest.raises(
        ValueError,
        match="max_size must be greater than zero",
    ):

        ExecutionHistory(
            max_size=max_size,
        )


@pytest.mark.parametrize(
    "max_size",
    [
        None,
        1.5,
        "100",
        [],
        {},
    ],
)
def test_non_integer_max_size_rejected(
    max_size,
):

    with pytest.raises(
        TypeError,
        match="max_size must be an integer",
    ):

        ExecutionHistory(
            max_size=max_size,
        )


def test_bool_max_size_rejected():

    with pytest.raises(
        TypeError,
        match="max_size must be an integer",
    ):

        ExecutionHistory(
            max_size=True,
        )


def test_empty_history_latest_returns_none():

    history = ExecutionHistory()

    assert history.latest() is None


def test_empty_history_all_returns_empty_list():

    history = ExecutionHistory()

    assert history.all() == []


def test_empty_history_length_is_zero():

    history = ExecutionHistory()

    assert len(history) == 0


def test_add_report():

    history = ExecutionHistory()

    report = make_report()

    history.add(
        report,
    )

    assert len(history) == 1

    assert history.latest() is report

    assert history.all() == [
        report,
    ]


def test_add_multiple_reports():

    history = ExecutionHistory()

    first = make_report(
        order_id="order-1",
    )

    second = make_report(
        order_id="order-2",
    )

    history.add(first)

    history.add(second)

    assert len(history) == 2

    assert history.latest() is second

    assert history.all() == [
        first,
        second,
    ]


def test_history_preserves_insertion_order():

    history = ExecutionHistory()

    reports = [
        make_report(
            order_id=f"order-{index}",
        )
        for index in range(5)
    ]

    for report in reports:

        history.add(
            report,
        )

    assert history.all() == reports


def test_oldest_report_is_evicted():

    history = ExecutionHistory(
        max_size=2,
    )

    first = make_report(
        order_id="order-1",
    )

    second = make_report(
        order_id="order-2",
    )

    third = make_report(
        order_id="order-3",
    )

    history.add(first)

    history.add(second)

    history.add(third)

    assert history.all() == [
        second,
        third,
    ]

    assert history.latest() is third


def test_max_size_one_keeps_only_latest_report():

    history = ExecutionHistory(
        max_size=1,
    )

    first = make_report(
        order_id="order-1",
    )

    second = make_report(
        order_id="order-2",
    )

    history.add(first)

    history.add(second)

    assert len(history) == 1

    assert history.latest() is second

    assert history.all() == [
        second,
    ]


@pytest.mark.parametrize(
    "invalid_report",
    [
        None,
        object(),
        {},
        [],
        "invalid",
        123,
    ],
)
def test_invalid_report_rejected(
    invalid_report,
):

    history = ExecutionHistory()

    with pytest.raises(
        TypeError,
        match="report must be an ExecutionReport",
    ):

        history.add(
            invalid_report,
        )


def test_clear_removes_all_reports():

    history = ExecutionHistory()

    history.add(
        make_report(),
    )

    history.add(
        make_report(
            order_id="order-2",
        ),
    )

    history.clear()

    assert len(history) == 0

    assert history.latest() is None

    assert history.all() == []


def test_all_returns_new_list():

    history = ExecutionHistory()

    report = make_report()

    history.add(
        report,
    )

    reports = history.all()

    reports.clear()

    assert len(history) == 1

    assert history.latest() is report


def test_max_size_property_is_read_only():

    history = ExecutionHistory(
        max_size=10,
    )

    assert history.max_size == 10

    with pytest.raises(
        AttributeError,
    ):

        history.max_size = 20


def test_reports_are_bounded():

    history = ExecutionHistory(
        max_size=3,
    )

    reports = [
        make_report(
            order_id=f"order-{index}",
        )
        for index in range(10)
    ]

    for report in reports:

        history.add(
            report,
        )

    assert len(history) == 3

    assert history.all() == reports[-3:]