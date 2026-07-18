import asyncio
import time

import pytest

from src.exchange.ratelimiter import RateLimiter


@pytest.mark.asyncio
async def test_create():

    limiter = RateLimiter(10)

    assert limiter.interval > 0


@pytest.mark.asyncio
async def test_acquire():

    limiter = RateLimiter(100)

    await limiter.acquire()

    await limiter.acquire()

    assert True


@pytest.mark.asyncio
async def test_delay():

    limiter = RateLimiter(2)

    start = time.perf_counter()

    await limiter.acquire()

    await limiter.acquire()

    elapsed = time.perf_counter() - start

    assert elapsed >= 0.45


def test_invalid():

    with pytest.raises(ValueError):

        RateLimiter(0)


@pytest.mark.asyncio
async def test_parallel():

    limiter = RateLimiter(20)

    await asyncio.gather(

        limiter.acquire(),

        limiter.acquire(),

        limiter.acquire(),

    )

    assert True