"""Tests for production order lifecycle tracking."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta, timezone
from fractions import Fraction
from math import inf, nan

import pytest

from src.execution.order_tracker import (
    OrderState,
    OrderStatus,
    OrderTracker,
)


INITIAL_TIME = datetime(
    2026,
    7,
    25,
    10,
    0,
    tzinfo=UTC,
)
UPDATED_TIME = datetime(
    2026,
    7,
    25,
    11,
    0,
    tzinfo=UTC,
)


def make_state(
    **overrides: object,
) -> OrderState:
    values: dict[str, object] = {
        "order_id": "order-1",
        "symbol": "BTCUSDT",
        "quantity": 1.0,
        "price": 100_000.0,
        "status": OrderStatus.CREATED,
        "updated_at": INITIAL_TIME,
    }
    values.update(overrides)

    return OrderState(
        **values,  # type: ignore[arg-type]
    )


def test_order_status_values() -> None:
    assert OrderStatus.CREATED.value == "CREATED"
    assert OrderStatus.SENT.value == "SENT"
    assert (
        OrderStatus.PARTIALLY_FILLED.value
        == "PARTIALLY_FILLED"
    )
    assert OrderStatus.FILLED.value == "FILLED"
    assert OrderStatus.CANCELLED.value == "CANCELLED"
    assert OrderStatus.REJECTED.value == "REJECTED"


@pytest.mark.parametrize(
    "status",
    [
        OrderStatus.CREATED,
        OrderStatus.SENT,
        OrderStatus.PARTIALLY_FILLED,
    ],
)
def test_active_status_property(
    status: OrderStatus,
) -> None:
    assert status.active is True
    assert status.terminal is False


@pytest.mark.parametrize(
    "status",
    [
        OrderStatus.FILLED,
        OrderStatus.CANCELLED,
        OrderStatus.REJECTED,
    ],
)
def test_terminal_status_property(
    status: OrderStatus,
) -> None:
    assert status.active is False
    assert status.terminal is True


def test_empty_tracker() -> None:
    tracker = OrderTracker()

    assert tracker.count() == 0
    assert len(tracker) == 0
    assert bool(tracker) is False
    assert tracker.all() == []
    assert tracker.snapshot() == ()
    assert tracker.active() == []
    assert tracker.terminal() == []
    assert list(tracker) == []


def test_add_order() -> None:
    tracker = OrderTracker()
    state = make_state()

    result = tracker.add(state)

    assert result is None
    assert tracker.exists("order-1") is True
    assert tracker.count() == 1
    assert bool(tracker) is True


def test_added_state_is_normalized() -> None:
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
    tracker = OrderTracker()

    tracker.add(
        make_state(
            order_id="  order-1  ",
            symbol="  BTCUSDT  ",
            quantity=1,
            price=100_000,
            updated_at=source_time,
        )
    )

    stored = tracker.get("order-1")

    assert stored.order_id == "order-1"
    assert stored.symbol == "BTCUSDT"
    assert stored.quantity == 1.0
    assert stored.price == 100_000.0
    assert stored.updated_at == INITIAL_TIME
    assert stored.updated_at.tzinfo is UTC


def test_fraction_numbers_are_supported() -> None:
    tracker = OrderTracker()

    tracker.add(
        make_state(
            quantity=Fraction(1, 2),
            price=Fraction(100, 1),
        )
    )

    stored = tracker.get("order-1")

    assert stored.quantity == 0.5
    assert stored.price == 100.0


def test_add_stores_defensive_copy() -> None:
    tracker = OrderTracker()
    source = make_state()

    tracker.add(source)
    source.symbol = "ETHUSDT"
    source.status = OrderStatus.FILLED

    stored = tracker.get("order-1")

    assert stored.symbol == "BTCUSDT"
    assert stored.status is OrderStatus.CREATED


def test_get_returns_defensive_copy() -> None:
    tracker = OrderTracker()
    tracker.add(make_state())

    first_read = tracker.get("order-1")
    first_read.status = OrderStatus.FILLED
    first_read.symbol = "ETHUSDT"

    second_read = tracker.get("order-1")

    assert second_read.status is OrderStatus.CREATED
    assert second_read.symbol == "BTCUSDT"


def test_duplicate_order_is_rejected() -> None:
    tracker = OrderTracker()
    tracker.add(make_state())

    with pytest.raises(
        ValueError,
        match="Order already exists",
    ):
        tracker.add(
            make_state(
                symbol="ETHUSDT",
            )
        )

    assert tracker.count() == 1


@pytest.mark.parametrize(
    "state",
    [
        None,
        object(),
        {},
        [],
        "state",
        1,
        True,
    ],
)
def test_add_rejects_invalid_state_type(
    state: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="state must be an OrderState",
    ):
        OrderTracker().add(
            state  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "field",
    [
        "order_id",
        "symbol",
    ],
)
@pytest.mark.parametrize(
    "value",
    [
        "",
        " ",
        "\t",
        "\n",
    ],
)
def test_add_rejects_empty_strings(
    field: str,
    value: str,
) -> None:
    with pytest.raises(
        ValueError,
        match=f"{field} cannot be empty",
    ):
        OrderTracker().add(
            make_state(
                **{
                    field: value,
                }
            )
        )


@pytest.mark.parametrize(
    "field",
    [
        "order_id",
        "symbol",
    ],
)
@pytest.mark.parametrize(
    "value",
    [
        None,
        1,
        True,
        object(),
    ],
)
def test_add_rejects_invalid_string_types(
    field: str,
    value: object,
) -> None:
    with pytest.raises(
        TypeError,
        match=f"{field} must be a string",
    ):
        OrderTracker().add(
            make_state(
                **{
                    field: value,
                }
            )
        )


def test_order_id_length_is_bounded() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "order_id must not exceed "
            "200 characters"
        ),
    ):
        OrderTracker().add(
            make_state(
                order_id="x" * 201,
            )
        )


def test_symbol_length_is_bounded() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "symbol must not exceed "
            "100 characters"
        ),
    ):
        OrderTracker().add(
            make_state(
                symbol="x" * 101,
            )
        )


@pytest.mark.parametrize(
    "field",
    [
        "quantity",
        "price",
    ],
)
@pytest.mark.parametrize(
    "value",
    [
        0,
        -1,
    ],
)
def test_add_rejects_non_positive_numbers(
    field: str,
    value: float,
) -> None:
    with pytest.raises(
        ValueError,
        match=f"{field} must be greater than zero",
    ):
        OrderTracker().add(
            make_state(
                **{
                    field: value,
                }
            )
        )


@pytest.mark.parametrize(
    "field",
    [
        "quantity",
        "price",
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
def test_add_rejects_non_finite_numbers(
    field: str,
    value: float,
) -> None:
    with pytest.raises(
        ValueError,
        match=f"{field} must be finite",
    ):
        OrderTracker().add(
            make_state(
                **{
                    field: value,
                }
            )
        )


@pytest.mark.parametrize(
    "field",
    [
        "quantity",
        "price",
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
def test_add_rejects_invalid_number_types(
    field: str,
    value: object,
) -> None:
    with pytest.raises(
        TypeError,
        match=f"{field} must be a number",
    ):
        OrderTracker().add(
            make_state(
                **{
                    field: value,
                }
            )
        )


@pytest.mark.parametrize(
    "status",
    [
        "CREATED",
        1,
        True,
        None,
        object(),
    ],
)
def test_add_rejects_invalid_status(
    status: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="status must be an OrderStatus",
    ):
        OrderTracker().add(
            make_state(
                status=status,
            )
        )


def test_naive_timestamp_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="updated_at must be timezone-aware",
    ):
        OrderTracker().add(
            make_state(
                updated_at=datetime(
                    2026,
                    7,
                    25,
                    10,
                    0,
                )
            )
        )


@pytest.mark.parametrize(
    "updated_at",
    [
        None,
        "2026-07-25",
        1,
        True,
        object(),
    ],
)
def test_invalid_timestamp_type_is_rejected(
    updated_at: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="updated_at must be a datetime",
    ):
        OrderTracker().add(
            make_state(
                updated_at=updated_at,
            )
        )


def test_update_order_status() -> None:
    tracker = OrderTracker(
        clock=lambda: UPDATED_TIME,
    )
    tracker.add(make_state())

    result = tracker.update_status(
        "order-1",
        OrderStatus.FILLED,
    )

    assert result is None

    state = tracker.get("order-1")

    assert state.status is OrderStatus.FILLED
    assert state.updated_at == UPDATED_TIME


def test_update_status_normalizes_order_id() -> None:
    tracker = OrderTracker(
        clock=lambda: UPDATED_TIME,
    )
    tracker.add(make_state())

    tracker.update_status(
        "  order-1  ",
        OrderStatus.SENT,
    )

    assert (
        tracker.get("order-1").status
        is OrderStatus.SENT
    )


def test_legacy_update_allows_unrestricted_transition() -> None:
    tracker = OrderTracker(
        clock=lambda: UPDATED_TIME,
    )
    tracker.add(
        make_state(
            status=OrderStatus.FILLED,
        )
    )

    tracker.update_status(
        "order-1",
        OrderStatus.CREATED,
    )

    assert (
        tracker.get("order-1").status
        is OrderStatus.CREATED
    )


def test_update_unknown_order() -> None:
    with pytest.raises(
        KeyError,
        match="Unknown order: missing",
    ):
        OrderTracker().update_status(
            "missing",
            OrderStatus.FILLED,
        )


@pytest.mark.parametrize(
    "status",
    [
        "FILLED",
        None,
        1,
        True,
        object(),
    ],
)
def test_update_rejects_invalid_status(
    status: object,
) -> None:
    tracker = OrderTracker()
    tracker.add(make_state())

    with pytest.raises(
        TypeError,
        match="status must be an OrderStatus",
    ):
        tracker.update_status(
            "order-1",
            status,  # type: ignore[arg-type]
        )

    assert (
        tracker.get("order-1").status
        is OrderStatus.CREATED
    )


def test_update_invalid_clock_preserves_state() -> None:
    tracker = OrderTracker(
        clock=lambda: datetime(
            2026,
            7,
            25,
            11,
            0,
        ),
    )
    tracker.add(make_state())

    with pytest.raises(
        ValueError,
        match="updated_at must be timezone-aware",
    ):
        tracker.update_status(
            "order-1",
            OrderStatus.SENT,
        )

    stored = tracker.get("order-1")

    assert stored.status is OrderStatus.CREATED
    assert stored.updated_at == INITIAL_TIME


def test_transition_created_to_sent() -> None:
    tracker = OrderTracker(
        clock=lambda: UPDATED_TIME,
    )
    tracker.add(make_state())

    tracker.transition_status(
        "order-1",
        OrderStatus.SENT,
    )

    assert (
        tracker.get("order-1").status
        is OrderStatus.SENT
    )


def test_transition_sent_to_partial_to_filled() -> None:
    times = iter(
        [
            datetime(
                2026,
                7,
                25,
                11,
                0,
                tzinfo=UTC,
            ),
            datetime(
                2026,
                7,
                25,
                12,
                0,
                tzinfo=UTC,
            ),
        ]
    )
    tracker = OrderTracker(
        clock=lambda: next(times),
    )
    tracker.add(
        make_state(
            status=OrderStatus.SENT,
        )
    )

    tracker.transition_status(
        "order-1",
        OrderStatus.PARTIALLY_FILLED,
    )
    tracker.transition_status(
        "order-1",
        OrderStatus.FILLED,
    )

    assert (
        tracker.get("order-1").status
        is OrderStatus.FILLED
    )


@pytest.mark.parametrize(
    ("current", "new"),
    [
        (
            OrderStatus.CREATED,
            OrderStatus.FILLED,
        ),
        (
            OrderStatus.FILLED,
            OrderStatus.SENT,
        ),
        (
            OrderStatus.CANCELLED,
            OrderStatus.FILLED,
        ),
        (
            OrderStatus.REJECTED,
            OrderStatus.CREATED,
        ),
    ],
)
def test_invalid_strict_transition(
    current: OrderStatus,
    new: OrderStatus,
) -> None:
    tracker = OrderTracker(
        clock=lambda: UPDATED_TIME,
    )
    tracker.add(
        make_state(
            status=current,
        )
    )

    with pytest.raises(
        ValueError,
        match=(
            "Invalid order status transition"
        ),
    ):
        tracker.transition_status(
            "order-1",
            new,
        )

    assert (
        tracker.get("order-1").status
        is current
    )


def test_idempotent_strict_transition_updates_time() -> None:
    tracker = OrderTracker(
        clock=lambda: UPDATED_TIME,
    )
    tracker.add(make_state())

    tracker.transition_status(
        "order-1",
        OrderStatus.CREATED,
    )

    state = tracker.get("order-1")

    assert state.status is OrderStatus.CREATED
    assert state.updated_at == UPDATED_TIME


@pytest.mark.parametrize(
    ("current", "new", "expected"),
    [
        (
            OrderStatus.CREATED,
            OrderStatus.SENT,
            True,
        ),
        (
            OrderStatus.CREATED,
            OrderStatus.CREATED,
            True,
        ),
        (
            OrderStatus.SENT,
            OrderStatus.FILLED,
            True,
        ),
        (
            OrderStatus.FILLED,
            OrderStatus.SENT,
            False,
        ),
    ],
)
def test_can_transition(
    current: OrderStatus,
    new: OrderStatus,
    expected: bool,
) -> None:
    assert OrderTracker.can_transition(
        current,
        new,
    ) is expected


def test_remove_order() -> None:
    tracker = OrderTracker()
    state = make_state()
    tracker.add(state)

    removed = tracker.remove(
        "order-1"
    )

    assert removed == state
    assert removed is not state
    assert tracker.exists("order-1") is False
    assert tracker.count() == 0


def test_remove_returns_defensive_copy() -> None:
    tracker = OrderTracker()
    tracker.add(make_state())

    removed = tracker.remove(
        "order-1"
    )
    removed.symbol = "ETHUSDT"

    assert tracker.count() == 0


def test_remove_unknown_order() -> None:
    with pytest.raises(
        KeyError,
        match="Unknown order: missing",
    ):
        OrderTracker().remove(
            "missing"
        )


def test_exists_normalizes_order_id() -> None:
    tracker = OrderTracker()
    tracker.add(make_state())

    assert tracker.exists(
        "  order-1  "
    ) is True


@pytest.mark.parametrize(
    "order_id",
    [
        "",
        " ",
        "\t",
        "\n",
    ],
)
def test_lookup_rejects_empty_order_id(
    order_id: str,
) -> None:
    tracker = OrderTracker()

    with pytest.raises(
        ValueError,
        match="order_id cannot be empty",
    ):
        tracker.exists(order_id)


@pytest.mark.parametrize(
    "order_id",
    [
        None,
        1,
        True,
        object(),
    ],
)
def test_lookup_rejects_invalid_order_id_type(
    order_id: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="order_id must be a string",
    ):
        OrderTracker().get(
            order_id  # type: ignore[arg-type]
        )


def test_all_preserves_insertion_order() -> None:
    tracker = OrderTracker()
    states = [
        make_state(
            order_id=f"order-{index}",
        )
        for index in range(5)
    ]
    tracker.add_many(states)

    assert tracker.all() == states


def test_all_returns_defensive_copies() -> None:
    tracker = OrderTracker()
    tracker.add(make_state())

    states = tracker.all()
    states[0].status = OrderStatus.FILLED
    states.clear()

    assert tracker.count() == 1
    assert (
        tracker.get("order-1").status
        is OrderStatus.CREATED
    )


def test_iterator_uses_independent_snapshot() -> None:
    tracker = OrderTracker()
    first = make_state(
        order_id="order-1",
    )
    second = make_state(
        order_id="order-2",
    )
    tracker.add_many(
        [
            first,
            second,
        ]
    )

    iterator = iter(tracker)
    tracker.remove("order-1")

    assert list(iterator) == [
        first,
        second,
    ]


def test_add_many() -> None:
    tracker = OrderTracker()
    states = [
        make_state(
            order_id="order-1",
        ),
        make_state(
            order_id="order-2",
        ),
    ]

    count = tracker.add_many(states)

    assert count == 2
    assert tracker.all() == states


def test_add_many_accepts_generator() -> None:
    tracker = OrderTracker()

    count = tracker.add_many(
        make_state(
            order_id=f"order-{index}",
        )
        for index in range(3)
    )

    assert count == 3
    assert tracker.count() == 3


def test_add_many_empty_iterable() -> None:
    tracker = OrderTracker()

    assert tracker.add_many([]) == 0
    assert tracker.count() == 0


@pytest.mark.parametrize(
    "states",
    [
        None,
        1,
        True,
        object(),
        "states",
        b"states",
        bytearray(b"states"),
    ],
)
def test_add_many_rejects_invalid_iterable(
    states: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="states must be an iterable",
    ):
        OrderTracker().add_many(
            states  # type: ignore[arg-type]
        )


def test_add_many_is_atomic_on_invalid_state() -> None:
    tracker = OrderTracker()
    original = make_state(
        order_id="original",
    )
    tracker.add(original)

    with pytest.raises(TypeError):
        tracker.add_many(
            [
                make_state(
                    order_id="valid",
                ),
                object(),  # type: ignore[list-item]
            ]
        )

    assert tracker.all() == [original]


def test_add_many_rejects_batch_duplicates_atomically() -> None:
    tracker = OrderTracker()

    with pytest.raises(
        ValueError,
        match="Duplicate order_id in states",
    ):
        tracker.add_many(
            [
                make_state(
                    order_id="duplicate",
                ),
                make_state(
                    order_id=" duplicate ",
                ),
            ]
        )

    assert tracker.count() == 0


def test_add_many_rejects_existing_duplicate_atomically() -> None:
    tracker = OrderTracker()
    original = make_state(
        order_id="existing",
    )
    tracker.add(original)

    with pytest.raises(
        ValueError,
        match="Order already exists",
    ):
        tracker.add_many(
            [
                make_state(
                    order_id="new",
                ),
                make_state(
                    order_id="existing",
                ),
            ]
        )

    assert tracker.all() == [original]


def test_by_status() -> None:
    tracker = OrderTracker()
    created = make_state(
        order_id="created",
        status=OrderStatus.CREATED,
    )
    filled = make_state(
        order_id="filled",
        status=OrderStatus.FILLED,
    )
    tracker.add_many(
        [
            created,
            filled,
        ]
    )

    assert tracker.by_status(
        OrderStatus.CREATED
    ) == [created]


def test_by_symbol() -> None:
    tracker = OrderTracker()
    btc = make_state(
        order_id="btc",
        symbol="BTCUSDT",
    )
    eth = make_state(
        order_id="eth",
        symbol="ETHUSDT",
    )
    tracker.add_many(
        [
            btc,
            eth,
        ]
    )

    assert tracker.by_symbol(
        "  BTCUSDT  "
    ) == [btc]


def test_active_and_terminal_filters() -> None:
    tracker = OrderTracker()
    created = make_state(
        order_id="created",
        status=OrderStatus.CREATED,
    )
    sent = make_state(
        order_id="sent",
        status=OrderStatus.SENT,
    )
    filled = make_state(
        order_id="filled",
        status=OrderStatus.FILLED,
    )
    rejected = make_state(
        order_id="rejected",
        status=OrderStatus.REJECTED,
    )
    tracker.add_many(
        [
            created,
            sent,
            filled,
            rejected,
        ]
    )

    assert tracker.active() == [
        created,
        sent,
    ]
    assert tracker.terminal() == [
        filled,
        rejected,
    ]


def test_filter_results_are_defensive_copies() -> None:
    tracker = OrderTracker()
    tracker.add(make_state())

    result = tracker.by_status(
        OrderStatus.CREATED
    )
    result[0].status = OrderStatus.FILLED

    assert (
        tracker.get("order-1").status
        is OrderStatus.CREATED
    )


def test_clear() -> None:
    tracker = OrderTracker()
    tracker.add_many(
        [
            make_state(
                order_id="order-1",
            ),
            make_state(
                order_id="order-2",
            ),
        ]
    )

    result = tracker.clear()

    assert result is None
    assert tracker.count() == 0


def test_order_state_properties() -> None:
    state = make_state(
        quantity=2,
        price=100,
        status=OrderStatus.SENT,
    )

    assert state.active is True
    assert state.terminal is False
    assert state.notional_value == 200.0


def test_invalid_clock_dependency() -> None:
    with pytest.raises(
        TypeError,
        match="clock must be callable",
    ):
        OrderTracker(
            clock=1,  # type: ignore[arg-type]
        )


def test_concurrent_additions_are_safe() -> None:
    tracker = OrderTracker()
    states = [
        make_state(
            order_id=f"order-{index}",
        )
        for index in range(500)
    ]

    with ThreadPoolExecutor(
        max_workers=16,
    ) as executor:
        list(
            executor.map(
                tracker.add,
                states,
            )
        )

    assert tracker.count() == 500
    assert len(
        {
            state.order_id
            for state in tracker.snapshot()
        }
    ) == 500