"""Concurrency-safe rate limiting for exchange I/O."""

from __future__ import annotations

import asyncio
import math
import time
from collections.abc import Awaitable, Callable
from threading import Lock

Clock = Callable[[], float]
AsyncSleeper = Callable[[float], Awaitable[None]]
SyncSleeper = Callable[[float], None]


class RateLimiter:
    """Enforce a minimum interval between weighted request permits.

    The limiter uses a monotonic virtual schedule. Permit reservations are
    atomic across asynchronous and synchronous callers, so concurrent callers
    cannot bypass the configured rate.

    A cancelled asynchronous caller keeps its reserved slot. This conservative
    behavior may delay later callers, but it prevents accidental exchange-rate
    limit violations during cancellation storms.
    """

    def __init__(
        self,
        requests_per_second: float = 1.0,
        *,
        clock: Clock = time.monotonic,
        async_sleep: AsyncSleeper = asyncio.sleep,
        sync_sleep: SyncSleeper = time.sleep,
    ) -> None:
        self.requests_per_second = self._validate_positive_number(
            requests_per_second,
            field_name="requests_per_second",
        )
        self.interval = 1.0 / self.requests_per_second

        if not callable(clock):
            raise TypeError("clock must be callable.")
        if not callable(async_sleep):
            raise TypeError("async_sleep must be callable.")
        if not callable(sync_sleep):
            raise TypeError("sync_sleep must be callable.")

        self._clock = clock
        self._async_sleep = async_sleep
        self._sync_sleep = sync_sleep

        self._state_lock = Lock()
        self._next_available_at: float | None = None
        self._last_request_at: float | None = None

    async def acquire(self, weight: float = 1.0) -> None:
        """Acquire one weighted asynchronous request permit."""

        delay = self._reserve(weight)

        if delay > 0:
            await self._async_sleep(delay)

        self._mark_acquired()

    def wait(self, weight: float = 1.0) -> None:
        """Acquire one weighted synchronous request permit.

        This compatibility API shares the same schedule as :meth:`acquire`.
        It must not be called from an event-loop thread because it blocks.
        """

        delay = self._reserve(weight)

        if delay > 0:
            self._sync_sleep(delay)

        self._mark_acquired()

    @property
    def last_request_at(self) -> float | None:
        """Return the monotonic time of the latest completed permit."""

        with self._state_lock:
            return self._last_request_at

    @property
    def retry_after(self) -> float:
        """Return the current delay before an immediate request permit."""

        now = self._read_clock()

        with self._state_lock:
            if self._next_available_at is None:
                return 0.0

            return max(0.0, self._next_available_at - now)

    def reset(self) -> None:
        """Clear all scheduling state.

        Reset should only be used when the remote exchange limit window is
        known to have reset, or in deterministic tests.
        """

        with self._state_lock:
            self._next_available_at = None
            self._last_request_at = None

    def _reserve(self, weight: float) -> float:
        normalized_weight = self._validate_positive_number(
            weight,
            field_name="weight",
        )
        now = self._read_clock()

        with self._state_lock:
            scheduled_at = (
                now
                if self._next_available_at is None
                else max(now, self._next_available_at)
            )
            delay = max(0.0, scheduled_at - now)
            self._next_available_at = (
                scheduled_at
                + self.interval * normalized_weight
            )

        return delay

    def _mark_acquired(self) -> None:
        acquired_at = self._read_clock()

        with self._state_lock:
            self._last_request_at = acquired_at

    def _read_clock(self) -> float:
        value = self._clock()

        if isinstance(value, bool) or not isinstance(
            value,
            (int, float),
        ):
            raise TypeError(
                "clock must return a finite numeric value."
            )

        normalized = float(value)

        if not math.isfinite(normalized):
            raise ValueError(
                "clock must return a finite numeric value."
            )

        return normalized

    @staticmethod
    def _validate_positive_number(
        value: float,
        *,
        field_name: str,
    ) -> float:
        if isinstance(value, bool) or not isinstance(
            value,
            (int, float),
        ):
            raise TypeError(f"{field_name} must be numeric.")

        normalized = float(value)

        if not math.isfinite(normalized):
            raise ValueError(f"{field_name} must be finite.")

        if normalized <= 0:
            raise ValueError(
                f"{field_name} must be greater than zero."
            )

        return normalized


__all__ = ("RateLimiter",)