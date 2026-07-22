from __future__ import annotations

import asyncio
import time


class RateLimiter:
    """
    Async rate limiter.

    requests_per_second=2
    یعنی حداقل 0.5 ثانیه فاصله بین درخواست‌ها.
    """

    def __init__(
        self,
        requests_per_second: float = 1.0,
    ) -> None:

        if isinstance(
            requests_per_second,
            bool,
        ):

            raise TypeError(
                "requests_per_second must be numeric."
            )

        if not isinstance(
            requests_per_second,
            (int, float),
        ):

            raise TypeError(
                "requests_per_second must be numeric."
            )

        if requests_per_second <= 0:

            raise ValueError(
                "requests_per_second must be greater than zero."
            )

        self.requests_per_second = float(
            requests_per_second,
        )

        self.interval = (
            1.0
            / self.requests_per_second
        )

        self._last_request_at: float | None = None

        self._lock = asyncio.Lock()

    # ==================================================
    # ASYNC API
    # ==================================================

    async def acquire(
        self,
    ) -> None:

        async with self._lock:

            now = time.monotonic()

            if (
                self._last_request_at
                is not None
            ):

                elapsed = (
                    now
                    - self._last_request_at
                )

                remaining = (
                    self.interval
                    - elapsed
                )

                if remaining > 0:

                    await asyncio.sleep(
                        remaining,
                    )

            self._last_request_at = (
                time.monotonic()
            )

    # ==================================================
    # SYNC COMPATIBILITY API
    # ==================================================

    def wait(
        self,
    ) -> None:

        now = time.monotonic()

        if (
            self._last_request_at
            is not None
        ):

            elapsed = (
                now
                - self._last_request_at
            )

            remaining = (
                self.interval
                - elapsed
            )

            if remaining > 0:

                time.sleep(
                    remaining,
                )

        self._last_request_at = (
            time.monotonic()
        )