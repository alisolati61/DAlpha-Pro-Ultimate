"""Tests for high-level execution coordination."""

from dataclasses import FrozenInstanceError
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
from src.risk.portfolio_guard import (
    PortfolioState,
)


def make_request(
    *,
    symbol: str = "BTCUSDT",
) -> ExecutionRequest:
    return ExecutionRequest(
        symbol=symbol,
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
def engine() -> Mock:
    return Mock(
        spec=ExecutionEngine,
    )


@pytest.fixture
def manager(
    engine: Mock,
) -> ExecutionManager:
    return ExecutionManager(
        engine,  # type: ignore[arg-type]
    )


def test_successful_execution_returns_success(
    manager: ExecutionManager,
    engine: Mock,
) -> None:
    engine.execute.return_value = True

    result = manager.execute(
        make_request()
    )

    assert result == ExecutionResult(
        success=True,
        message="Execution completed.",
    )
    assert result.success is True
    assert result.rejected is False
    assert bool(result) is True


def test_rejected_execution_returns_failure(
    manager: ExecutionManager,
    engine: Mock,
) -> None:
    engine.execute.return_value = False

    result = manager.execute(
        make_request()
    )

    assert result == ExecutionResult(
        success=False,
        message="Execution rejected.",
    )
    assert result.success is False
    assert result.rejected is True
    assert bool(result) is False


def test_engine_is_called_once(
    manager: ExecutionManager,
    engine: Mock,
) -> None:
    request = make_request()
    engine.execute.return_value = True

    manager.execute(request)

    engine.execute.assert_called_once_with(
        request
    )


@pytest.mark.parametrize(
    "invalid_engine",
    [
        None,
        object(),
        {},
        "engine",
        123,
        True,
    ],
)
def test_invalid_engine_is_rejected(
    invalid_engine: object,
) -> None:
    with pytest.raises(
        TypeError,
        match=(
            "engine must be an "
            "ExecutionEngine"
        ),
    ):
        ExecutionManager(
            invalid_engine  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "invalid_execution_request",
    [
        None,
        object(),
        {},
        "invalid",
        123,
        True,
        [],
    ],
)
def test_invalid_request_is_rejected(
    manager: ExecutionManager,
    engine: Mock,
    invalid_execution_request: object,
) -> None:
    with pytest.raises(
        TypeError,
        match=(
            "request must be an "
            "ExecutionRequest"
        ),
    ):
        manager.execute(
            invalid_execution_request  # type: ignore[arg-type]
        )

    engine.execute.assert_not_called()


def test_result_is_immutable(
    manager: ExecutionManager,
    engine: Mock,
) -> None:
    engine.execute.return_value = True

    result = manager.execute(
        make_request()
    )

    with pytest.raises(
        FrozenInstanceError,
    ):
        result.success = False  # type: ignore[misc]


def test_direct_result_construction_remains_available() -> None:
    result = ExecutionResult(
        success=True,
        message="Custom result.",
    )

    assert result.success is True
    assert result.message == "Custom result."


@pytest.mark.parametrize(
    "engine_result",
    [
        1,
        0,
        None,
        "yes",
        "",
        [],
        object(),
    ],
)
def test_engine_must_return_exact_bool(
    manager: ExecutionManager,
    engine: Mock,
    engine_result: object,
) -> None:
    engine.execute.return_value = engine_result

    with pytest.raises(
        TypeError,
        match=(
            "engine.execute must "
            "return a bool"
        ),
    ):
        manager.execute(
            make_request()
        )


def test_engine_exception_is_propagated(
    manager: ExecutionManager,
    engine: Mock,
) -> None:
    engine.execute.side_effect = RuntimeError(
        "exchange unavailable"
    )

    with pytest.raises(
        RuntimeError,
        match="exchange unavailable",
    ):
        manager.execute(
            make_request()
        )


def test_execute_many_preserves_order(
    manager: ExecutionManager,
    engine: Mock,
) -> None:
    requests = [
        make_request(
            symbol="BTCUSDT",
        ),
        make_request(
            symbol="ETHUSDT",
        ),
        make_request(
            symbol="SOLUSDT",
        ),
    ]
    engine.execute.side_effect = [
        True,
        False,
        True,
    ]

    results = manager.execute_many(
        requests
    )

    assert results == [
        ExecutionResult(
            True,
            "Execution completed.",
        ),
        ExecutionResult(
            False,
            "Execution rejected.",
        ),
        ExecutionResult(
            True,
            "Execution completed.",
        ),
    ]
    assert [
        call.args[0]
        for call in engine.execute.call_args_list
    ] == requests


def test_execute_many_accepts_generator(
    manager: ExecutionManager,
    engine: Mock,
) -> None:
    engine.execute.return_value = True

    results = manager.execute_many(
        make_request(
            symbol=f"ASSET-{index}",
        )
        for index in range(3)
    )

    assert len(results) == 3
    assert all(
        result.success
        for result in results
    )


def test_execute_many_empty_iterable(
    manager: ExecutionManager,
    engine: Mock,
) -> None:
    assert manager.execute_many([]) == []
    engine.execute.assert_not_called()


@pytest.mark.parametrize(
    "requests",
    [
        None,
        1,
        True,
        object(),
        "requests",
        b"requests",
        bytearray(b"requests"),
    ],
)
def test_execute_many_invalid_container(
    manager: ExecutionManager,
    engine: Mock,
    requests: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="requests must be an iterable",
    ):
        manager.execute_many(
            requests  # type: ignore[arg-type]
        )

    engine.execute.assert_not_called()


def test_execute_many_validates_all_before_execution(
    manager: ExecutionManager,
    engine: Mock,
) -> None:
    with pytest.raises(
        TypeError,
        match=(
            "request must be an "
            "ExecutionRequest"
        ),
    ):
        manager.execute_many(
            [
                make_request(),
                object(),  # type: ignore[list-item]
            ]
        )

    engine.execute.assert_not_called()


def test_execute_many_stops_on_engine_exception(
    manager: ExecutionManager,
    engine: Mock,
) -> None:
    requests = [
        make_request(
            symbol="BTCUSDT",
        ),
        make_request(
            symbol="ETHUSDT",
        ),
        make_request(
            symbol="SOLUSDT",
        ),
    ]
    engine.execute.side_effect = [
        True,
        RuntimeError(
            "exchange unavailable"
        ),
        True,
    ]

    with pytest.raises(
        RuntimeError,
        match="exchange unavailable",
    ):
        manager.execute_many(
            requests
        )

    assert engine.execute.call_count == 2


def test_iter_execute_is_lazy_after_validation(
    manager: ExecutionManager,
    engine: Mock,
) -> None:
    engine.execute.side_effect = [
        True,
        False,
    ]
    requests = [
        make_request(
            symbol="BTCUSDT",
        ),
        make_request(
            symbol="ETHUSDT",
        ),
    ]

    iterator = manager.iter_execute(
        requests
    )

    assert engine.execute.call_count == 0

    first = next(iterator)

    assert first.success is True
    assert engine.execute.call_count == 1

    second = next(iterator)

    assert second.success is False
    assert engine.execute.call_count == 2

    with pytest.raises(StopIteration):
        next(iterator)


def test_iter_execute_validates_before_first_engine_call(
    manager: ExecutionManager,
    engine: Mock,
) -> None:
    iterator = manager.iter_execute(
        [
            make_request(),
            object(),  # type: ignore[list-item]
        ]
    )

    with pytest.raises(
        TypeError,
        match=(
            "request must be an "
            "ExecutionRequest"
        ),
    ):
        next(iterator)

    engine.execute.assert_not_called()