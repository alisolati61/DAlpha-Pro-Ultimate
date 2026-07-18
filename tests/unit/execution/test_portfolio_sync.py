from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.execution.execution_report import (
    ExecutionReport,
)
from src.execution.portfolio_sync import (
    PortfolioSynchronizer,
)


def make_success_report(
    *,
    quantity: float = 2.0,
    price: float = 100.0,
) -> ExecutionReport:

    return ExecutionReport(
        order_id="order-1",
        symbol="BTC/USDT",
        success=True,
        quantity=quantity,
        executed_price=price,
        message="Order executed.",
        timestamp=datetime.now(UTC),
    )


def make_failed_report() -> ExecutionReport:

    return ExecutionReport(
        order_id="",
        symbol="BTC/USDT",
        success=False,
        quantity=0.0,
        executed_price=0.0,
        message="Order failed.",
        timestamp=datetime.now(UTC),
    )


def test_default_state():

    synchronizer = PortfolioSynchronizer()

    assert synchronizer.state.cash == 10_000.0
    assert synchronizer.state.position_size == 0.0
    assert synchronizer.state.average_price == 0.0


def test_initial_cash_is_stored():

    synchronizer = PortfolioSynchronizer(
        initial_cash=5_000,
    )

    assert synchronizer.state.cash == 5_000.0


def test_initial_cash_is_float():

    synchronizer = PortfolioSynchronizer(
        initial_cash=5_000,
    )

    assert isinstance(
        synchronizer.state.cash,
        float,
    )


def test_successful_execution_reduces_cash():

    synchronizer = PortfolioSynchronizer(
        initial_cash=10_000,
    )

    synchronizer.apply(
        make_success_report(
            quantity=2,
            price=100,
        ),
    )

    assert synchronizer.state.cash == 9_800.0


def test_successful_execution_increases_position_size():

    synchronizer = PortfolioSynchronizer()

    synchronizer.apply(
        make_success_report(
            quantity=2,
            price=100,
        ),
    )

    assert synchronizer.state.position_size == 2.0


def test_successful_execution_sets_average_price():

    synchronizer = PortfolioSynchronizer()

    synchronizer.apply(
        make_success_report(
            quantity=2,
            price=100,
        ),
    )

    assert synchronizer.state.average_price == 100.0


def test_weighted_average_price_is_calculated():

    synchronizer = PortfolioSynchronizer()

    synchronizer.apply(
        make_success_report(
            quantity=2,
            price=100,
        ),
    )

    synchronizer.apply(
        make_success_report(
            quantity=2,
            price=200,
        ),
    )

    assert (
        synchronizer.state.average_price
        == 150.0
    )


def test_weighted_average_price_with_different_sizes():

    synchronizer = PortfolioSynchronizer()

    synchronizer.apply(
        make_success_report(
            quantity=1,
            price=100,
        ),
    )

    synchronizer.apply(
        make_success_report(
            quantity=3,
            price=200,
        ),
    )

    assert (
        synchronizer.state.average_price
        == 175.0
    )


def test_multiple_executions_reduce_cash_correctly():

    synchronizer = PortfolioSynchronizer(
        initial_cash=10_000,
    )

    synchronizer.apply(
        make_success_report(
            quantity=1,
            price=100,
        ),
    )

    synchronizer.apply(
        make_success_report(
            quantity=2,
            price=200,
        ),
    )

    assert synchronizer.state.cash == 9_500.0


def test_multiple_executions_accumulate_position():

    synchronizer = PortfolioSynchronizer()

    synchronizer.apply(
        make_success_report(
            quantity=1,
            price=100,
        ),
    )

    synchronizer.apply(
        make_success_report(
            quantity=2,
            price=200,
        ),
    )

    assert synchronizer.state.position_size == 3.0


def test_failed_execution_does_not_change_cash():

    synchronizer = PortfolioSynchronizer()

    before = synchronizer.state.cash

    synchronizer.apply(
        make_failed_report(),
    )

    assert synchronizer.state.cash == before


def test_failed_execution_does_not_change_position():

    synchronizer = PortfolioSynchronizer()

    synchronizer.apply(
        make_failed_report(),
    )

    assert synchronizer.state.position_size == 0.0


def test_failed_execution_does_not_change_average_price():

    synchronizer = PortfolioSynchronizer()

    synchronizer.apply(
        make_failed_report(),
    )

    assert synchronizer.state.average_price == 0.0


def test_invalid_report_type_is_rejected():

    synchronizer = PortfolioSynchronizer()

    with pytest.raises(
        TypeError,
        match="report must be an ExecutionReport",
    ):

        synchronizer.apply(
            "invalid",
        )


@pytest.mark.parametrize(
    "cash",
    [
        -1,
        -0.01,
    ],
)
def test_negative_initial_cash_is_rejected(
    cash,
):

    with pytest.raises(
        ValueError,
        match="cash cannot be negative",
    ):

        PortfolioSynchronizer(
            initial_cash=cash,
        )


@pytest.mark.parametrize(
    "cash",
    [
        None,
        "1000",
        [],
        {},
    ],
)
def test_invalid_initial_cash_type_is_rejected(
    cash,
):

    with pytest.raises(
        TypeError,
        match="cash must be a number",
    ):

        PortfolioSynchronizer(
            initial_cash=cash,
        )


@pytest.mark.parametrize(
    "cash",
    [
        True,
        False,
    ],
)
def test_boolean_initial_cash_is_rejected(
    cash,
):

    with pytest.raises(
        TypeError,
        match="cash must be a number",
    ):

        PortfolioSynchronizer(
            initial_cash=cash,
        )


@pytest.mark.parametrize(
    "cash",
    [
        float("inf"),
        float("-inf"),
        float("nan"),
    ],
)
def test_non_finite_initial_cash_is_rejected(
    cash,
):

    with pytest.raises(
        ValueError,
        match="cash must be finite",
    ):

        PortfolioSynchronizer(
            initial_cash=cash,
        )


def test_reset_restores_default_cash():

    synchronizer = PortfolioSynchronizer(
        initial_cash=5_000,
    )

    synchronizer.apply(
        make_success_report(
            quantity=2,
            price=100,
        ),
    )

    synchronizer.reset()

    assert synchronizer.state.cash == 10_000.0
    assert synchronizer.state.position_size == 0.0
    assert synchronizer.state.average_price == 0.0


def test_reset_accepts_custom_cash():

    synchronizer = PortfolioSynchronizer()

    synchronizer.reset(
        cash=25_000,
    )

    assert synchronizer.state.cash == 25_000.0


def test_reset_rejects_negative_cash():

    synchronizer = PortfolioSynchronizer()

    with pytest.raises(
        ValueError,
        match="cash cannot be negative",
    ):

        synchronizer.reset(
            cash=-1,
        )


@pytest.mark.parametrize(
    "quantity",
    [
        0,
        -1,
    ],
)
def test_successful_report_rejects_invalid_quantity(
    quantity,
):

    synchronizer = PortfolioSynchronizer()

    with pytest.raises(
        ValueError,
        match="Successful execution quantity",
    ):

        synchronizer.apply(
            make_success_report(
                quantity=quantity,
                price=100,
            ),
        )


@pytest.mark.parametrize(
    "price",
    [
        0,
        -1,
    ],
)
def test_successful_report_rejects_invalid_price(
    price,
):

    synchronizer = PortfolioSynchronizer()

    with pytest.raises(
        ValueError,
        match="Successful execution price",
    ):

        synchronizer.apply(
            make_success_report(
                quantity=1,
                price=price,
            ),
        )


def test_state_values_remain_float():

    synchronizer = PortfolioSynchronizer()

    synchronizer.apply(
        make_success_report(
            quantity=1,
            price=100,
        ),
    )

    assert isinstance(
        synchronizer.state.cash,
        float,
    )

    assert isinstance(
        synchronizer.state.position_size,
        float,
    )

    assert isinstance(
        synchronizer.state.average_price,
        float,
    )