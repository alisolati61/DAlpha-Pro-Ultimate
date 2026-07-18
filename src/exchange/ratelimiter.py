from __future__ import annotations

import asyncio
import time


class RateLimiter:
    """
    Simple async token-bucket rate limiter.

    Example
    -------
    limiter = RateLimiter(10)

    await limiter.acquire()
    """

    def __init__(
        self,
        requests_per_second: float,
    ) -> None:

        if requests_per_second <= 0:
            raise ValueError(
                "requests_per_second must be positive."
            )

        self._interval = 1.0 / requests_per_second

        self._last_request = 0.0

        self._lock = asyncio.Lock()

    # ------------------------------------------------

    async def acquire(self) -> None:

        async with self._lock:

            now = time.perf_counter()

            elapsed = now - self._last_request

            wait = self._interval - elapsed

            if wait > 0:

                await asyncio.sleep(wait)

            self._last_request = time.perf_counter()

    # ------------------------------------------------

    @property
    def interval(self) -> float:

        return self._interval