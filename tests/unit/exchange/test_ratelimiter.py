"""Deterministic behavioral tests for the exchange rate limiter."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from src.exchange.ratelimiter import RateLimiter


class FakeTime:
    def __init__(self, start: float = 100.0) -> None:
        self.now = start
        self.async_delays: list[float] = []
        self.sync_delays: list[float] = []

    def monotonic(self) -> float:
        return self.now

    async def async_sleep(self, delay: float) -> None:
        self.async_delays.append(delay)
        self.now += delay
        await asyncio.sleep(0)

    def sync_sleep(self, delay: float) -> None:
        self.sync_delays.append(delay)
        self.now += delay

    def advance(self, seconds: float) -> None:
        self.now += seconds


def build_limiter(
    fake_time: FakeTime,
    requests_per_second: float = 2.0,
) -> RateLimiter:
    return RateLimiter(
        requests_per_second,
        clock=fake_time.monotonic,
        async_sleep=fake_time.async_sleep,
        sync_sleep=fake_time.sync_sleep,
    )


def run(coroutine: Any) -> Any:
    return asyncio.run(coroutine)


def test_configuration_exposes_rate_and_interval() -> None:
    limiter = RateLimiter(4)

    assert limiter.requests_per_second == 4.0
    assert limiter.interval == 0.25
    assert limiter.last_request_at is None


@pytest.mark.parametrize(
    "value",
    [True, None, "2", object()],
)
def test_non_numeric_rate_is_rejected(value: object) -> None:
    with pytest.raises(
        TypeError,
        match="requests_per_second must be numeric",
    ):
        RateLimiter(value)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "value",
    [0, -1, float("inf"), float("-inf"), float("nan")],
)
def test_invalid_numeric_rate_is_rejected(value: float) -> None:
    with pytest.raises(ValueError):
        RateLimiter(value)


@pytest.mark.parametrize(
    "field",
    ["clock", "async_sleep", "sync_sleep"],
)
def test_non_callable_dependency_is_rejected(field: str) -> None:
    kwargs = {field: object()}

    with pytest.raises(TypeError, match=f"{field} must be callable"):
        RateLimiter(1, **kwargs)  # type: ignore[arg-type]


def test_first_async_acquire_is_immediate() -> None:
    fake_time = FakeTime()
    limiter = build_limiter(fake_time)

    run(limiter.acquire())

    assert fake_time.async_delays == []
    assert limiter.last_request_at == 100.0
    assert limiter.retry_after == 0.5


def test_second_async_acquire_waits_exact_interval() -> None:
    fake_time = FakeTime()
    limiter = build_limiter(fake_time)

    async def scenario() -> None:
        await limiter.acquire()
        await limiter.acquire()

    run(scenario())

    assert fake_time.async_delays == [0.5]
    assert fake_time.now == 100.5
    assert limiter.last_request_at == 100.5
    assert limiter.retry_after == 0.5


def test_elapsed_time_reduces_required_delay() -> None:
    fake_time = FakeTime()
    limiter = build_limiter(
        fake_time,
        requests_per_second=1,
    )

    async def scenario() -> None:
        await limiter.acquire()
        fake_time.advance(0.25)
        await limiter.acquire()

    run(scenario())

    assert fake_time.async_delays == [0.75]
    assert fake_time.now == 101.0


def test_weight_reserves_multiple_rate_slots() -> None:
    fake_time = FakeTime()
    limiter = build_limiter(
        fake_time,
        requests_per_second=2,
    )

    async def scenario() -> None:
        await limiter.acquire(weight=3)
        await limiter.acquire()

    run(scenario())

    assert fake_time.async_delays == [1.5]
    assert fake_time.now == 101.5


@pytest.mark.parametrize(
    "weight",
    [True, None, "1", object()],
)
def test_non_numeric_weight_is_rejected(weight: object) -> None:
    fake_time = FakeTime()
    limiter = build_limiter(fake_time)

    with pytest.raises(
        TypeError,
        match="weight must be numeric",
    ):
        run(limiter.acquire(weight))  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "weight",
    [0, -1, float("inf"), float("nan")],
)
def test_invalid_numeric_weight_is_rejected(
    weight: float,
) -> None:
    fake_time = FakeTime()
    limiter = build_limiter(fake_time)

    with pytest.raises(ValueError):
        run(limiter.acquire(weight))


def test_sync_wait_uses_same_schedule_as_async_acquire() -> None:
    fake_time = FakeTime()
    limiter = build_limiter(
        fake_time,
        requests_per_second=4,
    )

    run(limiter.acquire())
    limiter.wait()

    assert fake_time.sync_delays == [0.25]
    assert fake_time.now == 100.25
    assert limiter.last_request_at == 100.25


def test_reset_clears_rate_limit_state() -> None:
    fake_time = FakeTime()
    limiter = build_limiter(fake_time)

    run(limiter.acquire())
    limiter.reset()
    run(limiter.acquire())

    assert fake_time.async_delays == []
    assert limiter.last_request_at == 100.0


def test_cancelled_wait_keeps_reserved_capacity() -> None:
    fake_time = FakeTime()
    sleep_calls = 0

    async def cancelling_sleep(delay: float) -> None:
        nonlocal sleep_calls
        sleep_calls += 1

        if sleep_calls == 1:
            raise asyncio.CancelledError

        fake_time.async_delays.append(delay)
        fake_time.now += delay

    limiter = RateLimiter(
        1,
        clock=fake_time.monotonic,
        async_sleep=cancelling_sleep,
        sync_sleep=fake_time.sync_sleep,
    )

    async def scenario() -> None:
        await limiter.acquire()

        with pytest.raises(asyncio.CancelledError):
            await limiter.acquire()

        await limiter.acquire()

    run(scenario())

    assert fake_time.async_delays == [2.0]
    assert fake_time.now == 102.0
    assert limiter.last_request_at == 102.0


def test_concurrent_callers_receive_serialized_slots() -> None:
    fake_time = FakeTime()
    limiter = build_limiter(
        fake_time,
        requests_per_second=2,
    )

    async def scenario() -> None:
        await asyncio.gather(
            limiter.acquire(),
            limiter.acquire(),
            limiter.acquire(),
        )

    run(scenario())

    assert fake_time.async_delays == [0.5, 0.5]
    assert fake_time.now == 101.0


@pytest.mark.parametrize(
    "clock_value",
    [True, "100", float("inf"), float("nan")],
)
def test_invalid_clock_result_is_rejected(
    clock_value: object,
) -> None:
    limiter = RateLimiter(
        1,
        clock=lambda: clock_value,  # type: ignore[return-value]
    )

    expected_error = (
        TypeError
        if isinstance(clock_value, (bool, str))
        else ValueError
    )

    with pytest.raises(expected_error):
        run(limiter.acquire())