"""Behavioral tests for reconnect retry orchestration."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from src.exchange.reconnect import ReconnectManager


class FakeSleeper:
    def __init__(self) -> None:
        self.delays: list[float] = []

    async def __call__(self, delay: float) -> None:
        self.delays.append(delay)
        await asyncio.sleep(0)


def run(coroutine: Any) -> Any:
    return asyncio.run(coroutine)


def test_success_on_first_attempt_does_not_sleep() -> None:
    sleeper = FakeSleeper()
    manager = ReconnectManager(
        retries=5,
        delay=1,
        sleep=sleeper,
    )
    calls = 0

    async def connect() -> bool:
        nonlocal calls
        calls += 1
        return True

    assert run(manager.run(connect)) is True
    assert calls == 1
    assert sleeper.delays == []
    assert manager.attempts_made == 1
    assert manager.last_error is None


def test_none_result_is_success_for_connection_compatibility() -> None:
    manager = ReconnectManager(retries=1, delay=0)

    async def connect() -> None:
        return None

    assert run(manager.run(connect)) is True
    assert manager.attempts_made == 1


def test_explicit_false_result_is_retried() -> None:
    sleeper = FakeSleeper()
    manager = ReconnectManager(
        retries=3,
        delay=0.5,
        backoff_factor=2,
        max_delay=10,
        sleep=sleeper,
    )
    results = iter([False, False, True])

    async def connect() -> bool:
        return next(results)

    assert run(manager.run(connect)) is True
    assert sleeper.delays == [0.5, 1.0]
    assert manager.attempts_made == 3
    assert manager.last_error is None


def test_retryable_exceptions_are_recorded_and_retried() -> None:
    sleeper = FakeSleeper()
    manager = ReconnectManager(
        retries=3,
        delay=1,
        sleep=sleeper,
    )
    failure = RuntimeError("network unavailable")
    calls = 0

    async def connect() -> bool:
        nonlocal calls
        calls += 1

        if calls < 3:
            raise failure

        return True

    assert run(manager.run(connect)) is True
    assert sleeper.delays == [1.0, 2.0]
    assert manager.attempts_made == 3
    assert manager.last_error is None


def test_exhaustion_returns_false_without_sleep_after_last_attempt() -> None:
    sleeper = FakeSleeper()
    manager = ReconnectManager(
        retries=3,
        delay=1,
        sleep=sleeper,
    )
    failure = OSError("still offline")

    async def connect() -> bool:
        raise failure

    assert run(manager.run(connect)) is False
    assert sleeper.delays == [1.0, 2.0]
    assert manager.attempts_made == 3
    assert manager.last_error is failure


def test_zero_retries_never_calls_callback() -> None:
    manager = ReconnectManager(retries=0, delay=0)
    called = False

    async def connect() -> bool:
        nonlocal called
        called = True
        return True

    assert run(manager.run(connect)) is False
    assert called is False
    assert manager.attempts_made == 0
    assert manager.last_error is None


def test_retry_predicate_can_fail_fast() -> None:
    sleeper = FakeSleeper()
    manager = ReconnectManager(
        retries=5,
        delay=1,
        sleep=sleeper,
    )
    failure = PermissionError("credentials rejected")

    async def connect() -> bool:
        raise failure

    with pytest.raises(PermissionError) as captured:
        run(
            manager.run(
                connect,
                retry_if=lambda exc: not isinstance(
                    exc,
                    PermissionError,
                ),
            )
        )

    assert captured.value is failure
    assert sleeper.delays == []
    assert manager.attempts_made == 1
    assert manager.last_error is failure


def test_cancelled_error_is_never_swallowed() -> None:
    manager = ReconnectManager(retries=5, delay=0)

    async def connect() -> bool:
        raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        run(manager.run(connect))

    assert manager.attempts_made == 1
    assert manager.last_error is None


def test_backoff_is_capped_by_max_delay() -> None:
    manager = ReconnectManager(
        retries=5,
        delay=2,
        backoff_factor=3,
        max_delay=10,
    )

    assert manager.delay_for_attempt(1) == 2.0
    assert manager.delay_for_attempt(2) == 6.0
    assert manager.delay_for_attempt(3) == 10.0
    assert manager.delay_for_attempt(10) == 10.0


@pytest.mark.parametrize(
    ("random_value", "expected"),
    [
        (0.0, 8.0),
        (0.5, 10.0),
        (1.0, 12.0),
    ],
)
def test_jitter_is_bounded_and_deterministic(
    random_value: float,
    expected: float,
) -> None:
    manager = ReconnectManager(
        retries=2,
        delay=10,
        max_delay=20,
        jitter=0.2,
        random_source=lambda: random_value,
    )

    assert manager.delay_for_attempt(1) == expected


def test_jitter_never_exceeds_max_delay() -> None:
    manager = ReconnectManager(
        retries=2,
        delay=10,
        max_delay=10,
        jitter=1,
        random_source=lambda: 1.0,
    )

    assert manager.delay_for_attempt(1) == 10.0


def test_concurrent_runs_are_serialized() -> None:
    manager = ReconnectManager(retries=1, delay=0)
    first_started = asyncio.Event()
    release_first = asyncio.Event()
    execution_order: list[str] = []

    async def first_connect() -> bool:
        execution_order.append("first-start")
        first_started.set()
        await release_first.wait()
        execution_order.append("first-end")
        return True

    async def second_connect() -> bool:
        execution_order.append("second")
        return True

    async def scenario() -> list[bool]:
        first_task = asyncio.create_task(
            manager.run(first_connect)
        )
        await first_started.wait()

        second_task = asyncio.create_task(
            manager.run(second_connect)
        )
        await asyncio.sleep(0)

        assert execution_order == ["first-start"]

        release_first.set()
        return await asyncio.gather(
            first_task,
            second_task,
        )

    assert run(scenario()) == [True, True]
    assert execution_order == [
        "first-start",
        "first-end",
        "second",
    ]


@pytest.mark.parametrize(
    ("kwargs", "error_type", "message"),
    [
        (
            {"retries": True},
            TypeError,
            "retries must be an integer",
        ),
        (
            {"retries": -1},
            ValueError,
            "retries must be greater",
        ),
        (
            {"delay": "1"},
            TypeError,
            "delay must be numeric",
        ),
        (
            {"delay": float("inf")},
            ValueError,
            "delay must be finite",
        ),
        (
            {"backoff_factor": 0.5},
            ValueError,
            "backoff_factor must be greater",
        ),
        (
            {"max_delay": -1},
            ValueError,
            "max_delay must be greater",
        ),
        (
            {"delay": 2, "max_delay": 1},
            ValueError,
            "max_delay must be greater",
        ),
        (
            {"jitter": 1.1},
            ValueError,
            "jitter must be between",
        ),
        (
            {"sleep": object()},
            TypeError,
            "sleep must be callable",
        ),
        (
            {"random_source": object()},
            TypeError,
            "random_source must be callable",
        ),
    ],
)
def test_invalid_configuration_is_rejected(
    kwargs: dict[str, object],
    error_type: type[Exception],
    message: str,
) -> None:
    with pytest.raises(error_type, match=message):
        ReconnectManager(**kwargs)  # type: ignore[arg-type]


def test_invalid_callback_and_predicate_are_rejected() -> None:
    manager = ReconnectManager(retries=1, delay=0)

    with pytest.raises(
        TypeError,
        match="connect_callback must be callable",
    ):
        run(manager.run(object()))  # type: ignore[arg-type]

    async def connect() -> bool:
        return True

    with pytest.raises(
        TypeError,
        match="retry_if must be callable",
    ):
        run(
            manager.run(
                connect,
                retry_if=object(),  # type: ignore[arg-type]
            )
        )


@pytest.mark.parametrize(
    ("failed_attempt", "error_type"),
    [
        (True, TypeError),
        (1.5, TypeError),
        (0, ValueError),
        (-1, ValueError),
    ],
)
def test_invalid_failed_attempt_is_rejected(
    failed_attempt: object,
    error_type: type[Exception],
) -> None:
    manager = ReconnectManager()

    with pytest.raises(error_type):
        manager.delay_for_attempt(  # type: ignore[arg-type]
            failed_attempt
        )


@pytest.mark.parametrize(
    ("random_value", "error_type"),
    [
        (True, TypeError),
        ("0.5", TypeError),
        (-0.1, ValueError),
        (1.1, ValueError),
        (float("nan"), ValueError),
    ],
)
def test_invalid_random_source_result_is_rejected(
    random_value: object,
    error_type: type[Exception],
) -> None:
    manager = ReconnectManager(
        delay=1,
        max_delay=2,
        jitter=0.5,
        random_source=lambda: random_value,  # type: ignore[return-value]
    )

    with pytest.raises(error_type):
        manager.delay_for_attempt(1)