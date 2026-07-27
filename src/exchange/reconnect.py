"""Deterministic retry orchestration for exchange reconnections."""

from __future__ import annotations

import asyncio
import math
import random
from collections.abc import Awaitable, Callable
from typing import Any, TypeAlias

ConnectCallback: TypeAlias = Callable[[], Awaitable[Any]]
RetryPredicate: TypeAlias = Callable[[Exception], bool]
AsyncSleeper: TypeAlias = Callable[[float], Awaitable[None]]
RandomSource: TypeAlias = Callable[[], float]


class ReconnectManager:
    """Run serialized reconnection attempts with bounded backoff.

    ``retries`` preserves the project's existing meaning: it is the maximum
    number of callback invocations, not the number of retries after an initial
    attempt.

    A callback result is considered successful unless it is explicitly
    ``False``. This keeps compatibility with connection methods that return
    ``None`` after establishing a connection.
    """

    def __init__(
        self,
        retries: int = 5,
        delay: float = 1.0,
        *,
        backoff_factor: float = 2.0,
        max_delay: float = 60.0,
        jitter: float = 0.0,
        sleep: AsyncSleeper = asyncio.sleep,
        random_source: RandomSource = random.random,
    ) -> None:
        self._retries = self._validate_retries(retries)
        self._delay = self._validate_non_negative_number(
            delay,
            field_name="delay",
        )
        self._backoff_factor = self._validate_backoff_factor(
            backoff_factor
        )
        self._max_delay = self._validate_non_negative_number(
            max_delay,
            field_name="max_delay",
        )
        self._jitter = self._validate_jitter(jitter)

        if self._max_delay < self._delay:
            raise ValueError(
                "max_delay must be greater than or equal to delay."
            )

        if not callable(sleep):
            raise TypeError("sleep must be callable.")

        if not callable(random_source):
            raise TypeError("random_source must be callable.")

        self._sleep = sleep
        self._random_source = random_source
        self._run_lock = asyncio.Lock()

        self._attempts_made = 0
        self._last_error: Exception | None = None

    @property
    def retries(self) -> int:
        """Return the maximum number of callback invocations."""

        return self._retries

    @property
    def delay(self) -> float:
        """Return the base retry delay in seconds."""

        return self._delay

    @property
    def backoff_factor(self) -> float:
        """Return the exponential backoff multiplier."""

        return self._backoff_factor

    @property
    def max_delay(self) -> float:
        """Return the upper delay bound in seconds."""

        return self._max_delay

    @property
    def jitter(self) -> float:
        """Return the proportional jitter bound."""

        return self._jitter

    @property
    def attempts_made(self) -> int:
        """Return attempts made by the latest completed run."""

        return self._attempts_made

    @property
    def last_error(self) -> Exception | None:
        """Return the latest retryable callback exception."""

        return self._last_error

    async def run(
        self,
        connect_callback: ConnectCallback,
        *,
        retry_if: RetryPredicate | None = None,
    ) -> bool:
        """Run the connection callback until success or exhaustion.

        Exceptions are retryable by default. When ``retry_if`` is supplied,
        exceptions rejected by that predicate are raised immediately.

        ``asyncio.CancelledError`` is never swallowed.
        """

        if not callable(connect_callback):
            raise TypeError("connect_callback must be callable.")

        if retry_if is not None and not callable(retry_if):
            raise TypeError("retry_if must be callable or None.")

        async with self._run_lock:
            self._attempts_made = 0
            self._last_error = None

            for attempt_index in range(self._retries):
                self._attempts_made = attempt_index + 1

                try:
                    result = await connect_callback()
                except Exception as exc:
                    self._last_error = exc

                    if retry_if is not None and not retry_if(exc):
                        raise
                else:
                    if result is not False:
                        self._last_error = None
                        return True

                if self._attempts_made >= self._retries:
                    break

                retry_delay = self.delay_for_attempt(
                    self._attempts_made
                )

                if retry_delay > 0:
                    await self._sleep(retry_delay)

            return False

    def delay_for_attempt(self, failed_attempt: int) -> float:
        """Return delay before the attempt following ``failed_attempt``."""

        if (
            isinstance(failed_attempt, bool)
            or not isinstance(failed_attempt, int)
        ):
            raise TypeError("failed_attempt must be an integer.")

        if failed_attempt < 1:
            raise ValueError(
                "failed_attempt must be greater than or equal to one."
            )

        base_delay = min(
            self._delay
            * (self._backoff_factor ** (failed_attempt - 1)),
            self._max_delay,
        )

        if base_delay == 0 or self._jitter == 0:
            return base_delay

        random_value = self._random_source()

        if (
            isinstance(random_value, bool)
            or not isinstance(random_value, (int, float))
        ):
            raise TypeError(
                "random_source must return a numeric value "
                "between zero and one."
            )

        normalized_random = float(random_value)

        if (
            not math.isfinite(normalized_random)
            or not 0.0 <= normalized_random <= 1.0
        ):
            raise ValueError(
                "random_source must return a finite value "
                "between zero and one."
            )

        jitter_multiplier = (
            1.0
            + ((normalized_random * 2.0) - 1.0) * self._jitter
        )

        return min(
            self._max_delay,
            max(0.0, base_delay * jitter_multiplier),
        )

    @staticmethod
    def _validate_retries(value: int) -> int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError("retries must be an integer.")

        if value < 0:
            raise ValueError("retries must be greater than or equal to zero.")

        return value

    @staticmethod
    def _validate_non_negative_number(
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

        if normalized < 0:
            raise ValueError(
                f"{field_name} must be greater than or equal to zero."
            )

        return normalized

    @staticmethod
    def _validate_backoff_factor(value: float) -> float:
        normalized = ReconnectManager._validate_non_negative_number(
            value,
            field_name="backoff_factor",
        )

        if normalized < 1:
            raise ValueError(
                "backoff_factor must be greater than or equal to one."
            )

        return normalized

    @staticmethod
    def _validate_jitter(value: float) -> float:
        normalized = ReconnectManager._validate_non_negative_number(
            value,
            field_name="jitter",
        )

        if normalized > 1:
            raise ValueError(
                "jitter must be between zero and one."
            )

        return normalized


__all__ = (
    "ConnectCallback",
    "ReconnectManager",
    "RetryPredicate",
)