import time

from src.data.data_cache import DataCache


def test_set():

    cache = DataCache()

    cache.set(
        "btc",
        100,
    )

    assert cache.size == 1


def test_get():

    cache = DataCache()

    cache.set(
        "btc",
        100,
    )

    assert cache.get("btc") == 100


def test_remove():

    cache = DataCache()

    cache.set(
        "btc",
        100,
    )

    cache.remove("btc")

    assert cache.get("btc") is None


def test_clear():

    cache = DataCache()

    cache.set("a", 1)

    cache.set("b", 2)

    cache.clear()

    assert cache.size == 0


def test_expiration():

    cache = DataCache(
        ttl_seconds=1,
    )

    cache.set(
        "btc",
        100,
    )

    time.sleep(1.2)

    assert cache.get("btc") is None


def test_result_types():

    cache = DataCache()

    cache.set(
        "btc",
        100,
    )

    value = cache.get("btc")

    assert isinstance(value, int)