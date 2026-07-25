"""Tests for thread-safe bounded execution history."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import pytest

from src.execution.execution_history import (
    ExecutionHistory,
)
from src.execution.execution_report import (
    ExecutionReport,
    ExecutionReportFactory,
)


FIXED_TIME = datetime(
    2026,
    7,
    25,
    12,
    0,
    tzinfo=UTC,
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
        timestamp=FIXED_TIME,
    )


def test_default_max_size_is_1000() -> None:
    history = ExecutionHistory()

    assert history.max_size == 1000
    assert history.remaining_capacity == 1000
    assert history.is_full is False


@pytest.mark.parametrize(
    "max_size",
    [
        0,
        -1,
        -100,
    ],
)
def test_invalid_max_size_rejected(
    max_size: int,
) -> None:
    with pytest.raises(
        ValueError,
        match=(
            "max_size must be greater "
            "than zero"
        ),
    ):
        ExecutionHistory(
            max_size=max_size,
        )


@pytest.mark.parametrize(
    "max_size",
    [
        True,
        False,
        None,
        1.5,
        "100",
        [],
        {},
        object(),
    ],
)
def test_non_integer_max_size_rejected(
    max_size: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="max_size must be an integer",
    ):
        ExecutionHistory(
            max_size=max_size,  # type: ignore[arg-type]
        )


def test_empty_history_state() -> None:
    history = ExecutionHistory()

    assert history.latest() is None
    assert history.all() == []
    assert history.snapshot() == ()
    assert len(history) == 0
    assert bool(history) is False
    assert list(history) == []
    assert history.successful_count == 0
    assert history.failed_count == 0


def test_add_report_preserves_identity() -> None:
    history = ExecutionHistory()
    report = make_report()

    history.add(report)

    assert len(history) == 1
    assert history.latest() is report
    assert history.all() == [report]
    assert bool(history) is True


def test_add_multiple_reports_preserves_order() -> None:
    history = ExecutionHistory()
    reports = [
        make_report(
            order_id=f"order-{index}",
        )
        for index in range(5)
    ]

    for report in reports:
        history.add(report)

    assert history.all() == reports
    assert list(history) == reports
    assert history.latest() is reports[-1]


def test_oldest_report_is_evicted() -> None:
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
    assert history.is_full is True
    assert history.remaining_capacity == 0


def test_max_size_one_keeps_only_latest() -> None:
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

    assert history.all() == [second]


@pytest.mark.parametrize(
    "invalid_report",
    [
        None,
        object(),
        {},
        [],
        "invalid",
        123,
        True,
    ],
)
def test_invalid_report_rejected(
    invalid_report: object,
) -> None:
    history = ExecutionHistory()

    with pytest.raises(
        TypeError,
        match=(
            "report must be an "
            "ExecutionReport"
        ),
    ):
        history.add(
            invalid_report,  # type: ignore[arg-type]
        )

    assert len(history) == 0


def test_clear_removes_all_reports() -> None:
    history = ExecutionHistory()
    history.extend(
        [
            make_report(),
            make_report(
                order_id="order-2",
            ),
        ]
    )

    result = history.clear()

    assert result is None
    assert len(history) == 0
    assert history.latest() is None
    assert history.all() == []


def test_all_returns_new_list() -> None:
    history = ExecutionHistory()
    report = make_report()
    history.add(report)

    reports = history.all()
    reports.clear()

    assert history.all() == [report]


def test_snapshot_is_immutable_tuple() -> None:
    history = ExecutionHistory()
    report = make_report()
    history.add(report)

    snapshot = history.snapshot()

    assert snapshot == (report,)
    assert type(snapshot) is tuple


def test_iterator_uses_independent_snapshot() -> None:
    history = ExecutionHistory(
        max_size=3,
    )
    first = make_report(
        order_id="order-1",
    )
    second = make_report(
        order_id="order-2",
    )
    history.extend(
        [
            first,
            second,
        ]
    )

    iterator = iter(history)
    history.add(
        make_report(
            order_id="order-3",
        )
    )

    assert list(iterator) == [
        first,
        second,
    ]


def test_max_size_property_is_read_only() -> None:
    history = ExecutionHistory(
        max_size=10,
    )

    with pytest.raises(
        AttributeError,
    ):
        history.max_size = 20  # type: ignore[misc]


def test_capacity_properties() -> None:
    history = ExecutionHistory(
        max_size=3,
    )

    assert history.remaining_capacity == 3
    assert history.is_full is False

    history.add(make_report())

    assert history.remaining_capacity == 2

    history.extend(
        [
            make_report(
                order_id="order-2",
            ),
            make_report(
                order_id="order-3",
            ),
        ]
    )

    assert history.remaining_capacity == 0
    assert history.is_full is True


def test_extend_appends_reports() -> None:
    history = ExecutionHistory()
    reports = [
        make_report(
            order_id="order-1",
        ),
        make_report(
            order_id="order-2",
        ),
    ]

    count = history.extend(reports)

    assert count == 2
    assert history.all() == reports


def test_extend_accepts_generator() -> None:
    history = ExecutionHistory()

    count = history.extend(
        make_report(
            order_id=f"order-{index}",
        )
        for index in range(3)
    )

    assert count == 3
    assert len(history) == 3


def test_extend_empty_iterable() -> None:
    history = ExecutionHistory()

    assert history.extend([]) == 0
    assert len(history) == 0


@pytest.mark.parametrize(
    "reports",
    [
        None,
        1,
        True,
        object(),
        "reports",
        b"reports",
        bytearray(b"reports"),
    ],
)
def test_extend_rejects_invalid_iterable(
    reports: object,
) -> None:
    history = ExecutionHistory()

    with pytest.raises(
        TypeError,
        match="reports must be an iterable",
    ):
        history.extend(
            reports,  # type: ignore[arg-type]
        )


def test_extend_is_atomic_when_item_is_invalid() -> None:
    history = ExecutionHistory()
    original = make_report(
        order_id="original",
    )
    history.add(original)

    with pytest.raises(
        TypeError,
        match=(
            "report must be an "
            "ExecutionReport"
        ),
    ):
        history.extend(
            [
                make_report(
                    order_id="valid",
                ),
                object(),  # type: ignore[list-item]
            ]
        )

    assert history.all() == [original]


def test_extend_respects_capacity() -> None:
    history = ExecutionHistory(
        max_size=3,
    )
    reports = [
        make_report(
            order_id=f"order-{index}",
        )
        for index in range(10)
    ]

    history.extend(reports)

    assert history.all() == reports[-3:]


@pytest.mark.parametrize(
    ("limit", "expected_ids"),
    [
        (
            1,
            ["order-4"],
        ),
        (
            2,
            [
                "order-3",
                "order-4",
            ],
        ),
        (
            5,
            [
                "order-0",
                "order-1",
                "order-2",
                "order-3",
                "order-4",
            ],
        ),
        (
            100,
            [
                "order-0",
                "order-1",
                "order-2",
                "order-3",
                "order-4",
            ],
        ),
    ],
)
def test_recent_returns_newest_in_order(
    limit: int,
    expected_ids: list[str],
) -> None:
    history = ExecutionHistory()
    history.extend(
        make_report(
            order_id=f"order-{index}",
        )
        for index in range(5)
    )

    assert [
        report.order_id
        for report in history.recent(limit)
    ] == expected_ids


def test_recent_on_empty_history() -> None:
    assert ExecutionHistory().recent(5) == []


@pytest.mark.parametrize(
    "limit",
    [
        0,
        -1,
    ],
)
def test_recent_rejects_non_positive_limit(
    limit: int,
) -> None:
    with pytest.raises(
        ValueError,
        match=(
            "limit must be greater "
            "than zero"
        ),
    ):
        ExecutionHistory().recent(limit)


@pytest.mark.parametrize(
    "limit",
    [
        True,
        False,
        1.5,
        "1",
        None,
        object(),
    ],
)
def test_recent_rejects_invalid_limit_type(
    limit: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="limit must be an integer",
    ):
        ExecutionHistory().recent(
            limit  # type: ignore[arg-type]
        )


def test_find_by_order_id_returns_newest_match() -> None:
    history = ExecutionHistory()
    first = make_report(
        order_id="duplicate",
        price=100,
    )
    second = make_report(
        order_id="other",
    )
    newest = make_report(
        order_id="duplicate",
        price=200,
    )
    history.extend(
        [
            first,
            second,
            newest,
        ]
    )

    assert (
        history.find_by_order_id(
            "duplicate"
        )
        is newest
    )


def test_find_by_order_id_normalizes_input() -> None:
    history = ExecutionHistory()
    report = make_report(
        order_id="order-1",
    )
    history.add(report)

    assert (
        history.find_by_order_id(
            "  order-1  "
        )
        is report
    )


def test_find_by_order_id_returns_none() -> None:
    history = ExecutionHistory()
    history.add(make_report())

    assert (
        history.find_by_order_id(
            "missing"
        )
        is None
    )


@pytest.mark.parametrize(
    "order_id",
    [
        "",
        " ",
        "\t",
        "\n",
    ],
)
def test_find_rejects_empty_order_id(
    order_id: str,
) -> None:
    with pytest.raises(
        ValueError,
        match="order_id cannot be empty",
    ):
        ExecutionHistory().find_by_order_id(
            order_id
        )


@pytest.mark.parametrize(
    "order_id",
    [
        None,
        1,
        True,
        object(),
    ],
)
def test_find_rejects_invalid_order_id_type(
    order_id: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="order_id must be a string",
    ):
        ExecutionHistory().find_by_order_id(
            order_id  # type: ignore[arg-type]
        )


def test_find_order_id_length_is_bounded() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "order_id must not exceed "
            "200 characters"
        ),
    ):
        ExecutionHistory().find_by_order_id(
            "x" * 201
        )


def test_for_symbol_preserves_order() -> None:
    history = ExecutionHistory()
    btc_one = make_report(
        order_id="btc-1",
        symbol="BTCUSDT",
    )
    eth = make_report(
        order_id="eth-1",
        symbol="ETHUSDT",
    )
    btc_two = make_report(
        order_id="btc-2",
        symbol="BTCUSDT",
        success=False,
    )
    history.extend(
        [
            btc_one,
            eth,
            btc_two,
        ]
    )

    assert history.for_symbol(
        "BTCUSDT"
    ) == [
        btc_one,
        btc_two,
    ]


def test_for_symbol_filters_success() -> None:
    history = ExecutionHistory()
    success = make_report(
        order_id="success",
        success=True,
    )
    failure = make_report(
        order_id="failure",
        success=False,
    )
    history.extend(
        [
            success,
            failure,
        ]
    )

    assert history.for_symbol(
        "BTCUSDT",
        success=True,
    ) == [success]

    assert history.for_symbol(
        "BTCUSDT",
        success=False,
    ) == [failure]


def test_for_symbol_normalizes_input() -> None:
    history = ExecutionHistory()
    report = make_report()
    history.add(report)

    assert history.for_symbol(
        "  BTCUSDT  "
    ) == [report]


def test_for_symbol_returns_new_list() -> None:
    history = ExecutionHistory()
    report = make_report()
    history.add(report)

    result = history.for_symbol(
        "BTCUSDT"
    )
    result.clear()

    assert history.all() == [report]


@pytest.mark.parametrize(
    "success",
    [
        1,
        "True",
        object(),
    ],
)
def test_for_symbol_rejects_invalid_success(
    success: object,
) -> None:
    with pytest.raises(
        TypeError,
        match=(
            "success must be a bool "
            "or None"
        ),
    ):
        ExecutionHistory().for_symbol(
            "BTCUSDT",
            success=success,  # type: ignore[arg-type]
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
def test_for_symbol_rejects_empty_symbol(
    symbol: str,
) -> None:
    with pytest.raises(
        ValueError,
        match="symbol cannot be empty",
    ):
        ExecutionHistory().for_symbol(
            symbol
        )


@pytest.mark.parametrize(
    "symbol",
    [
        None,
        1,
        True,
        object(),
    ],
)
def test_for_symbol_rejects_invalid_symbol_type(
    symbol: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="symbol must be a string",
    ):
        ExecutionHistory().for_symbol(
            symbol  # type: ignore[arg-type]
        )


def test_outcome_counts() -> None:
    history = ExecutionHistory()
    history.extend(
        [
            make_report(
                order_id="success-1",
                success=True,
            ),
            make_report(
                order_id="failure",
                success=False,
            ),
            make_report(
                order_id="success-2",
                success=True,
            ),
        ]
    )

    assert history.successful_count == 2
    assert history.failed_count == 1


def test_factory_reports_integrate_with_history() -> None:
    history = ExecutionHistory()
    success = ExecutionReportFactory.success(
        order_id="order-1",
        symbol="BTCUSDT",
        quantity=1,
        price=100,
        timestamp=FIXED_TIME,
    )
    failure = ExecutionReportFactory.failed(
        symbol="BTCUSDT",
        message="Rejected",
        timestamp=FIXED_TIME,
    )

    history.extend(
        [
            success,
            failure,
        ]
    )

    assert history.latest() is failure
    assert history.successful_count == 1
    assert history.failed_count == 1


def test_concurrent_additions_are_bounded_and_safe() -> None:
    history = ExecutionHistory(
        max_size=100,
    )

    reports = [
        make_report(
            order_id=f"order-{index}",
        )
        for index in range(500)
    ]

    with ThreadPoolExecutor(
        max_workers=16,
    ) as executor:
        list(
            executor.map(
                history.add,
                reports,
            )
        )

    assert len(history) == 100
    assert history.is_full is True
    assert history.remaining_capacity == 0
    assert all(
        isinstance(
            report,
            ExecutionReport,
        )
        for report in history.snapshot()
    )