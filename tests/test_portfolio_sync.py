"""Tests for safe execution-report portfolio synchronization."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from fractions import Fraction
from math import inf, nan

import pytest

from src.execution.execution_report import (
    ExecutionReport,
    ExecutionReportFactory,
)
from src.execution.portfolio_sync import (
    PortfolioState,
    PortfolioSynchronizer,
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
    *,
    order_id: str = "order-1",
    success: bool = True,
    quantity: object = 2.0,
    price: object = 100.0,
) -> ExecutionReport:
    return ExecutionReport(
        order_id=order_id,
        symbol="BTC/USDT",
        success=success,
        quantity=quantity,  # type: ignore[arg-type]
        executed_price=price,  # type: ignore[arg-type]
        message=(
            "Order executed."
            if success
            else "Order failed."
        ),
        timestamp=FIXED_TIME,
    )


def test_default_state() -> None:
    synchronizer = PortfolioSynchronizer()

    assert synchronizer.state.cash == 10_000.0
    assert synchronizer.state.position_size == 0.0
    assert synchronizer.state.average_price == 0.0
    assert synchronizer.state.is_flat is True
    assert synchronizer.state.position_cost == 0.0


def test_initial_cash_is_float() -> None:
    synchronizer = PortfolioSynchronizer(
        initial_cash=5_000,
    )

    assert synchronizer.state.cash == 5_000.0
    assert type(synchronizer.state.cash) is float


def test_fraction_initial_cash_supported() -> None:
    synchronizer = PortfolioSynchronizer(
        initial_cash=Fraction(3, 2),
    )

    assert synchronizer.state.cash == 1.5


@pytest.mark.parametrize(
    "cash",
    [-1, -0.01],
)
def test_negative_initial_cash_rejected(
    cash: float,
) -> None:
    with pytest.raises(
        ValueError,
        match="cash cannot be negative",
    ):
        PortfolioSynchronizer(cash)


@pytest.mark.parametrize(
    "cash",
    [None, "1000", [], {}, object(), True, False],
)
def test_invalid_initial_cash_type(
    cash: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="cash must be a number",
    ):
        PortfolioSynchronizer(
            cash  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "cash",
    [inf, -inf, nan],
)
def test_non_finite_initial_cash(
    cash: float,
) -> None:
    with pytest.raises(
        ValueError,
        match="cash must be finite",
    ):
        PortfolioSynchronizer(cash)


def test_state_property_preserves_live_identity() -> None:
    synchronizer = PortfolioSynchronizer()

    first = synchronizer.state
    second = synchronizer.state

    assert first is second


def test_snapshot_is_independent() -> None:
    synchronizer = PortfolioSynchronizer()

    snapshot = synchronizer.snapshot()
    snapshot.cash = 0

    assert synchronizer.state.cash == 10_000.0


def test_apply_successful_report() -> None:
    synchronizer = PortfolioSynchronizer()

    result = synchronizer.apply(
        make_report(
            quantity=2,
            price=100,
        )
    )

    assert result is None
    assert synchronizer.state.cash == 9_800.0
    assert synchronizer.state.position_size == 2.0
    assert synchronizer.state.average_price == 100.0
    assert synchronizer.state.is_flat is False


def test_weighted_average_equal_sizes() -> None:
    synchronizer = PortfolioSynchronizer()

    synchronizer.apply(
        make_report(
            quantity=2,
            price=100,
        )
    )
    synchronizer.apply(
        make_report(
            quantity=2,
            price=200,
        )
    )

    assert synchronizer.state.cash == 9_400.0
    assert synchronizer.state.position_size == 4.0
    assert synchronizer.state.average_price == 150.0
    assert synchronizer.position_cost() == 600.0


def test_weighted_average_different_sizes() -> None:
    synchronizer = PortfolioSynchronizer()

    synchronizer.apply(
        make_report(
            quantity=1,
            price=100,
        )
    )
    synchronizer.apply(
        make_report(
            quantity=3,
            price=200,
        )
    )

    assert synchronizer.state.position_size == 4.0
    assert synchronizer.state.average_price == 175.0


def test_fraction_execution_values() -> None:
    synchronizer = PortfolioSynchronizer(
        initial_cash=1_000,
    )

    synchronizer.apply(
        make_report(
            quantity=Fraction(1, 2),
            price=Fraction(201, 2),
        )
    )

    assert synchronizer.state.cash == 949.75
    assert synchronizer.state.position_size == 0.5
    assert synchronizer.state.average_price == 100.5


def test_failed_report_is_noop() -> None:
    synchronizer = PortfolioSynchronizer()
    state = synchronizer.state

    result = synchronizer.apply(
        make_report(
            success=False,
            quantity=0,
            price=0,
        )
    )

    assert result is None
    assert synchronizer.state is state
    assert synchronizer.state == PortfolioState(
        cash=10_000.0,
        position_size=0.0,
        average_price=0.0,
    )


def test_failed_report_does_not_validate_numbers() -> None:
    synchronizer = PortfolioSynchronizer()

    synchronizer.apply(
        make_report(
            success=False,
            quantity="invalid",
            price=object(),
        )
    )

    assert synchronizer.state.is_flat is True


@pytest.mark.parametrize(
    "report",
    [None, "invalid", 1, True, [], {}, object()],
)
def test_invalid_report_type(
    report: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="report must be an ExecutionReport",
    ):
        PortfolioSynchronizer().apply(
            report  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "success",
    [1, 0, "yes", None, object()],
)
def test_invalid_success_type(
    success: object,
) -> None:
    report = make_report()
    malformed = ExecutionReport(
        order_id=report.order_id,
        symbol=report.symbol,
        success=success,  # type: ignore[arg-type]
        quantity=report.quantity,
        executed_price=report.executed_price,
        message=report.message,
        timestamp=report.timestamp,
    )

    with pytest.raises(
        TypeError,
        match="report success must be a bool",
    ):
        PortfolioSynchronizer().apply(
            malformed
        )


@pytest.mark.parametrize(
    "quantity",
    [0, -1, -0.1],
)
def test_invalid_success_quantity_value(
    quantity: float,
) -> None:
    with pytest.raises(
        ValueError,
        match="Successful execution quantity",
    ):
        PortfolioSynchronizer().apply(
            make_report(
                quantity=quantity,
            )
        )


@pytest.mark.parametrize(
    "quantity",
    [nan, inf, -inf],
)
def test_non_finite_success_quantity(
    quantity: float,
) -> None:
    with pytest.raises(
        ValueError,
        match=(
            "Successful execution quantity "
            "must be finite"
        ),
    ):
        PortfolioSynchronizer().apply(
            make_report(
                quantity=quantity,
            )
        )


@pytest.mark.parametrize(
    "quantity",
    [None, "1", [], {}, True, False, object()],
)
def test_invalid_success_quantity_type(
    quantity: object,
) -> None:
    with pytest.raises(
        TypeError,
        match=(
            "Successful execution quantity "
            "must be a number"
        ),
    ):
        PortfolioSynchronizer().apply(
            make_report(
                quantity=quantity,
            )
        )


@pytest.mark.parametrize(
    "price",
    [0, -1, -0.1],
)
def test_invalid_success_price_value(
    price: float,
) -> None:
    with pytest.raises(
        ValueError,
        match="Successful execution price",
    ):
        PortfolioSynchronizer().apply(
            make_report(
                price=price,
            )
        )


@pytest.mark.parametrize(
    "price",
    [nan, inf, -inf],
)
def test_non_finite_success_price(
    price: float,
) -> None:
    with pytest.raises(
        ValueError,
        match=(
            "Successful execution price "
            "must be finite"
        ),
    ):
        PortfolioSynchronizer().apply(
            make_report(
                price=price,
            )
        )


@pytest.mark.parametrize(
    "price",
    [None, "100", [], {}, True, False, object()],
)
def test_invalid_success_price_type(
    price: object,
) -> None:
    with pytest.raises(
        TypeError,
        match=(
            "Successful execution price "
            "must be a number"
        ),
    ):
        PortfolioSynchronizer().apply(
            make_report(
                price=price,
            )
        )


def test_cost_overflow_rejected_atomically() -> None:
    synchronizer = PortfolioSynchronizer(
        initial_cash=1e308,
    )

    with pytest.raises(
        ValueError,
        match="Successful execution cost must be finite",
    ):
        synchronizer.apply(
            make_report(
                quantity=1e308,
                price=1e308,
            )
        )

    assert synchronizer.state == PortfolioState(
        cash=1e308,
        position_size=0.0,
        average_price=0.0,
    )


def test_insufficient_cash_rejected_atomically() -> None:
    synchronizer = PortfolioSynchronizer(
        initial_cash=100,
    )

    with pytest.raises(
        ValueError,
        match="Insufficient cash",
    ):
        synchronizer.apply(
            make_report(
                quantity=2,
                price=100,
            )
        )

    assert synchronizer.state.cash == 100.0
    assert synchronizer.state.is_flat is True


def test_exact_cash_is_allowed() -> None:
    synchronizer = PortfolioSynchronizer(
        initial_cash=200,
    )

    synchronizer.apply(
        make_report(
            quantity=2,
            price=100,
        )
    )

    assert synchronizer.state.cash == 0.0
    assert synchronizer.state.position_size == 2.0


def test_apply_mutates_existing_state_identity() -> None:
    synchronizer = PortfolioSynchronizer()
    state = synchronizer.state

    synchronizer.apply(make_report())

    assert synchronizer.state is state


def test_corrupted_live_state_is_rejected_without_further_mutation() -> None:
    synchronizer = PortfolioSynchronizer()
    synchronizer.state.cash = -1

    with pytest.raises(
        ValueError,
        match="cash cannot be negative",
    ):
        synchronizer.apply(make_report())

    assert synchronizer.state.cash == -1


def test_corrupted_flat_average_price_rejected() -> None:
    synchronizer = PortfolioSynchronizer()
    synchronizer.state.average_price = 100

    with pytest.raises(
        ValueError,
        match=(
            "average_price must be zero "
            "when position_size is zero"
        ),
    ):
        synchronizer.apply(make_report())


def test_apply_many() -> None:
    synchronizer = PortfolioSynchronizer()

    count = synchronizer.apply_many(
        [
            make_report(
                quantity=1,
                price=100,
            ),
            make_report(
                success=False,
                quantity=0,
                price=0,
            ),
            make_report(
                quantity=2,
                price=200,
            ),
        ]
    )

    assert count == 2
    assert synchronizer.state.cash == 9_500.0
    assert synchronizer.state.position_size == 3.0
    assert (
        synchronizer.state.average_price
        == pytest.approx(500 / 3)
    )


def test_apply_many_accepts_generator() -> None:
    synchronizer = PortfolioSynchronizer()

    count = synchronizer.apply_many(
        make_report(
            order_id=f"order-{index}",
            quantity=1,
            price=10,
        )
        for index in range(3)
    )

    assert count == 3
    assert synchronizer.state.position_size == 3.0


def test_apply_many_empty_iterable() -> None:
    synchronizer = PortfolioSynchronizer()

    assert synchronizer.apply_many([]) == 0
    assert synchronizer.state.is_flat is True


@pytest.mark.parametrize(
    "reports",
    [None, 1, True, object(), "reports", b"reports"],
)
def test_apply_many_invalid_container(
    reports: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="reports must be an iterable",
    ):
        PortfolioSynchronizer().apply_many(
            reports  # type: ignore[arg-type]
        )


def test_apply_many_is_atomic_on_invalid_report() -> None:
    synchronizer = PortfolioSynchronizer()
    original = synchronizer.snapshot()

    with pytest.raises(TypeError):
        synchronizer.apply_many(
            [
                make_report(),
                object(),  # type: ignore[list-item]
            ]
        )

    assert synchronizer.state == original


def test_apply_many_is_atomic_on_insufficient_cash() -> None:
    synchronizer = PortfolioSynchronizer(
        initial_cash=250,
    )

    with pytest.raises(
        ValueError,
        match="Insufficient cash",
    ):
        synchronizer.apply_many(
            [
                make_report(
                    quantity=1,
                    price=100,
                ),
                make_report(
                    quantity=2,
                    price=100,
                ),
            ]
        )

    assert synchronizer.state == PortfolioState(
        cash=250.0,
        position_size=0.0,
        average_price=0.0,
    )


def test_apply_once() -> None:
    synchronizer = PortfolioSynchronizer()

    assert synchronizer.apply_once(
        make_report(
            order_id="order-1",
        )
    ) is True
    assert synchronizer.apply_once(
        make_report(
            order_id=" order-1 ",
        )
    ) is False

    assert synchronizer.state.position_size == 2.0
    assert synchronizer.has_applied("order-1") is True
    assert synchronizer.applied_order_ids() == (
        "order-1",
    )


def test_apply_remains_non_idempotent_for_legacy() -> None:
    synchronizer = PortfolioSynchronizer()
    report = make_report(
        order_id="same",
        quantity=1,
        price=10,
    )

    synchronizer.apply(report)
    synchronizer.apply(report)

    assert synchronizer.state.position_size == 2.0


def test_apply_once_failed_report_is_ignored() -> None:
    synchronizer = PortfolioSynchronizer()

    assert synchronizer.apply_once(
        make_report(
            success=False,
            order_id="",
            quantity=0,
            price=0,
        )
    ) is False
    assert synchronizer.applied_order_ids() == ()


@pytest.mark.parametrize(
    "order_id",
    ["", " ", "\t", "\n"],
)
def test_apply_once_requires_order_id(
    order_id: str,
) -> None:
    with pytest.raises(
        ValueError,
        match="order_id cannot be empty",
    ):
        PortfolioSynchronizer().apply_once(
            make_report(
                order_id=order_id,
            )
        )


@pytest.mark.parametrize(
    "order_id",
    [None, 1, True, object()],
)
def test_apply_once_invalid_order_id_type(
    order_id: object,
) -> None:
    report = make_report()
    malformed = ExecutionReport(
        order_id=order_id,  # type: ignore[arg-type]
        symbol=report.symbol,
        success=True,
        quantity=report.quantity,
        executed_price=report.executed_price,
        message=report.message,
        timestamp=report.timestamp,
    )

    with pytest.raises(
        TypeError,
        match="order_id must be a string",
    ):
        PortfolioSynchronizer().apply_once(
            malformed
        )


def test_apply_once_order_id_length_bounded() -> None:
    with pytest.raises(
        ValueError,
        match="order_id must not exceed 200 characters",
    ):
        PortfolioSynchronizer().apply_once(
            make_report(
                order_id="x" * 201,
            )
        )


def test_factory_report_integration() -> None:
    synchronizer = PortfolioSynchronizer()

    report = ExecutionReportFactory.success(
        order_id="order-1",
        symbol="BTC/USDT",
        quantity=2,
        price=100,
        timestamp=FIXED_TIME,
    )

    synchronizer.apply(report)

    assert synchronizer.state.cash == 9_800.0


def test_market_value_pnl_and_equity() -> None:
    synchronizer = PortfolioSynchronizer(
        initial_cash=1_000,
    )
    synchronizer.apply(
        make_report(
            quantity=2,
            price=100,
        )
    )

    assert synchronizer.position_cost() == 200.0
    assert synchronizer.market_value(120) == 240.0
    assert synchronizer.unrealized_pnl(120) == 40.0
    assert synchronizer.equity(120) == 1_040.0


def test_flat_market_metrics() -> None:
    synchronizer = PortfolioSynchronizer(
        initial_cash=1_000,
    )

    assert synchronizer.market_value(100) == 0.0
    assert synchronizer.unrealized_pnl(100) == 0.0
    assert synchronizer.equity(100) == 1_000.0


@pytest.mark.parametrize(
    "price",
    [0, -1, nan, inf, -inf],
)
def test_invalid_mark_price_value(
    price: float,
) -> None:
    with pytest.raises(ValueError):
        PortfolioSynchronizer().market_value(
            price
        )


@pytest.mark.parametrize(
    "price",
    [None, "100", True, [], object()],
)
def test_invalid_mark_price_type(
    price: object,
) -> None:
    with pytest.raises(TypeError):
        PortfolioSynchronizer().market_value(
            price  # type: ignore[arg-type]
        )


def test_reset_default() -> None:
    synchronizer = PortfolioSynchronizer(
        initial_cash=5_000,
    )
    synchronizer.apply_once(
        make_report(
            order_id="order-1",
        )
    )

    result = synchronizer.reset()

    assert result is None
    assert synchronizer.state == PortfolioState(
        cash=10_000.0,
        position_size=0.0,
        average_price=0.0,
    )
    assert synchronizer.applied_order_ids() == ()


def test_reset_custom_cash() -> None:
    synchronizer = PortfolioSynchronizer()

    synchronizer.reset(cash=25_000)

    assert synchronizer.state.cash == 25_000.0
    assert type(synchronizer.state.cash) is float


def test_failed_reset_is_atomic() -> None:
    synchronizer = PortfolioSynchronizer(
        initial_cash=500,
    )
    synchronizer.apply(
        make_report(
            quantity=1,
            price=100,
        )
    )
    before = synchronizer.state

    with pytest.raises(ValueError):
        synchronizer.reset(cash=-1)

    assert synchronizer.state is before
    assert synchronizer.state.cash == 400.0


def test_reset_replaces_state_identity() -> None:
    synchronizer = PortfolioSynchronizer()
    before = synchronizer.state

    synchronizer.reset()

    assert synchronizer.state is not before


def test_state_values_remain_exact_floats() -> None:
    synchronizer = PortfolioSynchronizer()

    synchronizer.apply(
        make_report(
            quantity=1,
            price=100,
        )
    )

    assert type(synchronizer.state.cash) is float
    assert type(
        synchronizer.state.position_size
    ) is float
    assert type(
        synchronizer.state.average_price
    ) is float


def test_concurrent_apply_is_safe() -> None:
    synchronizer = PortfolioSynchronizer(
        initial_cash=10_000,
    )
    reports = [
        make_report(
            order_id=f"order-{index}",
            quantity=1,
            price=1,
        )
        for index in range(500)
    ]

    with ThreadPoolExecutor(
        max_workers=16,
    ) as executor:
        list(
            executor.map(
                synchronizer.apply,
                reports,
            )
        )

    assert synchronizer.state.cash == 9_500.0
    assert synchronizer.state.position_size == 500.0
    assert synchronizer.state.average_price == 1.0