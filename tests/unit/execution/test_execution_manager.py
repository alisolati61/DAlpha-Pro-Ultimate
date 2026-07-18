from __future__ import annotations

from unittest.mock import Mock

import pytest

from src.execution.execution_engine import (
    ExecutionEngine,
    ExecutionRequest,
)
from src.execution.execution_manager import (
    ExecutionManager,
    ExecutionResult,
)
from src.risk.portfolio_guard import PortfolioState


def make_request() -> ExecutionRequest:

    return ExecutionRequest(
        symbol="BTCUSDT",
        quantity=1.0,
        price=100.0,
        leverage=1.0,
        stop_loss=95.0,
        portfolio=PortfolioState(
            balance=10_000.0,
            equity=10_000.0,
            used_margin=0.0,
            open_positions=0,
            daily_loss=0.0,
            total_risk=0.0,
        ),
    )


@pytest.fixture
def engine():

    return Mock(
        spec=ExecutionEngine,
    )


@pytest.fixture
def manager(
    engine,
):

    return ExecutionManager(
        engine,
    )


def test_successful_execution_returns_success(
    manager,
    engine,
):

    engine.execute.return_value = True

    result = manager.execute(
        make_request(),
    )

    assert isinstance(
        result,
        ExecutionResult,
    )

    assert result.success is True

    assert (
        result.message
        == "Execution completed."
    )


def test_rejected_execution_returns_failure(
    manager,
    engine,
):

    engine.execute.return_value = False

    result = manager.execute(
        make_request(),
    )

    assert result.success is False

    assert (
        result.message
        == "Execution rejected."
    )


def test_engine_is_called_once(
    manager,
    engine,
):

    execution_request = make_request()

    engine.execute.return_value = True

    manager.execute(
        execution_request,
    )

    engine.execute.assert_called_once_with(
        execution_request,
    )


def test_invalid_engine_is_rejected():

    with pytest.raises(
        TypeError,
        match="engine must be an ExecutionEngine",
    ):

        ExecutionManager(
            object(),
        )


@pytest.mark.parametrize(
    "invalid_execution_request",
    [
        None,
        object(),
        {},
        "invalid",
        123,
    ],
)
def test_invalid_request_is_rejected(
    manager,
    invalid_execution_request,
):

    with pytest.raises(
        TypeError,
        match="request must be an ExecutionRequest",
    ):

        manager.execute(
            invalid_execution_request,
        )


def test_result_is_immutable(
    manager,
    engine,
):

    engine.execute.return_value = True

    result = manager.execute(
        make_request(),
    )

    with pytest.raises(
        AttributeError,
    ):

        result.success = False


def test_execution_result_fields_are_correct(
    manager,
    engine,
):

    engine.execute.return_value = True

    result = manager.execute(
        make_request(),
    )

    assert result.success is True

    assert isinstance(
        result.message,
        str,
    )

    assert result.message


def test_engine_exception_is_propagated(
    manager,
    engine,
):

    engine.execute.side_effect = RuntimeError(
        "exchange unavailable",
    )

    with pytest.raises(
        RuntimeError,
        match="exchange unavailable",
    ):

        manager.execute(
            make_request(),
        )