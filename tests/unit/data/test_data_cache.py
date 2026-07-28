"""Tests for deterministic local cache expiration."""

from __future__ import annotations

from math import inf, nan
from threading import Thread

import pytest

from src.data.data_cache import DataCache


class Clock:
    def __init__(self) -> None:
        self.value = 0.0

    def __call__(self) -> float:
        return self.value


def test_set_get_remove_clear_and_size() -> None:
    cache = DataCache()
    cache.set("a", 1)
    cache.set("b", 2)

    assert cache.get("a") == 1
    assert cache.size == 2

    cache.remove("a")
    assert cache.get("a") is None
    cache.clear()
    assert cache.size == 0


@pytest.mark.parametrize("ttl", [0, -1, True, nan, inf, -inf])
def test_ttl_must_be_finite_and_positive(ttl: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        DataCache(ttl_seconds=ttl)  # type: ignore[arg-type]


def test_expiration_boundary_and_purge_are_deterministic() -> None:
    clock = Clock()
    cache = DataCache(ttl_seconds=10, timer=clock)
    cache.set("first", 1)
    cache.set("second", 2)

    clock.value = 9.999
    assert cache.get("first") == 1

    clock.value = 10.0
    assert cache.get("first") is None
    assert cache.size == 0

    clock.value = 20.0
    cache.set("new", 3)
    assert cache.purge_expired() == 0
    clock.value = 30.0
    assert cache.purge_expired() == 1


@pytest.mark.parametrize("key", ["", " ", None, 123])
def test_keys_are_validated(key: object) -> None:
    cache = DataCache()
    with pytest.raises((TypeError, ValueError)):
        cache.set(key, 1)  # type: ignore[arg-type]
    with pytest.raises((TypeError, ValueError)):
        cache.get(key)  # type: ignore[arg-type]


def test_concurrent_set_and_get_is_safe() -> None:
    cache = DataCache()

    def worker(index: int) -> None:
        for value in range(100):
            key = f"{index}:{value}"
            cache.set(key, value)
            assert cache.get(key) == value

    threads = [Thread(target=worker, args=(index,)) for index in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert cache.size == 800
