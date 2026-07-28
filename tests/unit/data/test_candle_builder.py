"""Behavioral and compatibility tests for candle aggregation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from threading import Thread

import pytest

from src.data.candle_builder import (
    Candle,
    CandleBuilder,
)


def test_first_tick_preserves_public_contract() -> None:
    builder = CandleBuilder()

    candle = builder.update(
        "BTCUSDT",
        "1m",
        100,
        5,
    )

    assert isinstance(candle, Candle)
    assert candle.open == 100.0
    assert candle.high == 100.0
    assert candle.low == 100.0
    assert candle.close == 100.0
    assert candle.volume == 5.0
    assert candle.start_time.tzinfo is UTC


def test_subsequent_ticks_update_high_low_close_and_volume() -> None:
    builder = CandleBuilder()
    first = builder.update(
        "BTCUSDT",
        "1m",
        100,
        2,
    )
    second = builder.update(
        "BTCUSDT",
        "1m",
        120,
        3,
    )
    third = builder.update(
        "BTCUSDT",
        "1m",
        90,
        4,
    )

    assert first is second is third
    assert third.open == 100.0
    assert third.high == 120.0
    assert third.low == 90.0
    assert third.close == 90.0
    assert third.volume == 9.0


def test_latest_and_clear_remain_backward_compatible() -> None:
    builder = CandleBuilder()
    created = builder.update(
        "BTCUSDT",
        "1m",
        100,
        1,
    )

    assert builder.latest("BTCUSDT", "1m") is created
    assert builder.size == 1

    builder.clear()

    assert builder.latest("BTCUSDT", "1m") is None
    assert builder.size == 0


def test_symbol_and_timeframe_keys_are_trimmed_consistently() -> None:
    builder = CandleBuilder()

    candle = builder.update(
        " BTCUSDT ",
        " 1m ",
        100,
        1,
    )

    assert candle.symbol == "BTCUSDT"
    assert candle.timeframe == "1m"
    assert builder.latest(" BTCUSDT ", " 1m ") is candle


def test_keys_remain_case_sensitive_for_backward_compatibility() -> None:
    builder = CandleBuilder()

    upper = builder.update("BTCUSDT", "1m", 100, 1)
    lower = builder.update("btcusdt", "1m", 101, 1)

    assert upper is not lower
    assert builder.size == 2


def test_each_symbol_and_timeframe_has_independent_state() -> None:
    builder = CandleBuilder()

    btc_1m = builder.update("BTCUSDT", "1m", 100, 1)
    btc_5m = builder.update("BTCUSDT", "5m", 200, 2)
    eth_1m = builder.update("ETHUSDT", "1m", 300, 3)

    assert builder.latest("BTCUSDT", "1m") is btc_1m
    assert builder.latest("BTCUSDT", "5m") is btc_5m
    assert builder.latest("ETHUSDT", "1m") is eth_1m
    assert builder.size == 3


def test_naive_timestamp_is_interpreted_as_utc() -> None:
    timestamp = datetime(2026, 1, 1, 12, 30)

    candle = CandleBuilder().update(
        "BTCUSDT",
        "1m",
        100,
        1,
        timestamp,
    )

    assert candle.start_time == timestamp.replace(tzinfo=UTC)


def test_aware_timestamp_is_converted_to_utc() -> None:
    local_tz = timezone(timedelta(hours=3, minutes=30))
    timestamp = datetime(
        2026,
        1,
        1,
        12,
        30,
        tzinfo=local_tz,
    )

    candle = CandleBuilder().update(
        "BTCUSDT",
        "1m",
        100,
        1,
        timestamp,
    )

    assert candle.start_time == datetime(
        2026,
        1,
        1,
        9,
        0,
        tzinfo=UTC,
    )


def test_start_time_is_kept_from_first_tick() -> None:
    builder = CandleBuilder()
    first_timestamp = datetime(2026, 1, 1, tzinfo=UTC)
    later_timestamp = datetime(2026, 1, 2, tzinfo=UTC)

    candle = builder.update(
        "BTCUSDT",
        "1m",
        100,
        1,
        first_timestamp,
    )
    builder.update(
        "BTCUSDT",
        "1m",
        101,
        1,
        later_timestamp,
    )

    assert candle.start_time == first_timestamp


@pytest.mark.parametrize(
    ("field_name", "value", "message"),
    [
        ("symbol", "", "symbol cannot be empty"),
        ("symbol", "   ", "symbol cannot be empty"),
        ("symbol", 123, "symbol must be a string"),
        ("timeframe", "", "timeframe cannot be empty"),
        ("timeframe", None, "timeframe must be a string"),
    ],
)
def test_invalid_key_fields_are_rejected(
    field_name: str,
    value: object,
    message: str,
) -> None:
    kwargs: dict[str, object] = {
        "symbol": "BTCUSDT",
        "timeframe": "1m",
        "price": 100,
        "volume": 1,
    }
    kwargs[field_name] = value

    with pytest.raises(
        (TypeError, ValueError),
        match=message,
    ):
        CandleBuilder().update(**kwargs)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("field_name", "value", "message"),
    [
        ("price", 0, "price must be greater than zero"),
        ("price", -1, "price must be greater than zero"),
        ("price", True, "price must be numeric"),
        ("price", "bad", "price must be numeric"),
        ("price", float("nan"), "price must be finite"),
        ("price", float("inf"), "price must be finite"),
        ("volume", -1, "volume must be greater than or equal"),
        ("volume", True, "volume must be numeric"),
        ("volume", float("nan"), "volume must be finite"),
        ("volume", float("inf"), "volume must be finite"),
    ],
)
def test_invalid_numeric_tick_values_are_rejected(
    field_name: str,
    value: object,
    message: str,
) -> None:
    kwargs: dict[str, object] = {
        "symbol": "BTCUSDT",
        "timeframe": "1m",
        "price": 100,
        "volume": 1,
    }
    kwargs[field_name] = value

    with pytest.raises(
        (TypeError, ValueError),
        match=message,
    ):
        CandleBuilder().update(**kwargs)  # type: ignore[arg-type]


def test_timestamp_must_be_datetime() -> None:
    with pytest.raises(
        TypeError,
        match="timestamp must be a datetime",
    ):
        CandleBuilder().update(
            "BTCUSDT",
            "1m",
            100,
            1,
            timestamp=1_700_000_000,  # type: ignore[arg-type]
        )


def test_invalid_update_does_not_mutate_existing_candle() -> None:
    builder = CandleBuilder()
    candle = builder.update(
        "BTCUSDT",
        "1m",
        100,
        2,
    )
    snapshot = (
        candle.open,
        candle.high,
        candle.low,
        candle.close,
        candle.volume,
        candle.start_time,
    )

    with pytest.raises(ValueError):
        builder.update(
            "BTCUSDT",
            "1m",
            float("nan"),
            5,
        )

    assert (
        candle.open,
        candle.high,
        candle.low,
        candle.close,
        candle.volume,
        candle.start_time,
    ) == snapshot


def test_cumulative_volume_overflow_is_atomic() -> None:
    builder = CandleBuilder()
    candle = builder.update(
        "BTCUSDT",
        "1m",
        100,
        1.0e308,
    )

    with pytest.raises(
        ValueError,
        match="cumulative volume must be finite",
    ):
        builder.update(
            "BTCUSDT",
            "1m",
            101,
            1.0e308,
        )

    assert candle.high == 100.0
    assert candle.low == 100.0
    assert candle.close == 100.0
    assert candle.volume == 1.0e308


def test_direct_candle_construction_normalizes_types() -> None:
    candle = Candle(
        symbol=" BTCUSDT ",
        timeframe=" 1m ",
        open="100",  # type: ignore[arg-type]
        high="110",  # type: ignore[arg-type]
        low="90",  # type: ignore[arg-type]
        close="105",  # type: ignore[arg-type]
        volume="10",  # type: ignore[arg-type]
        start_time=datetime(2026, 1, 1),
    )

    assert candle.symbol == "BTCUSDT"
    assert candle.timeframe == "1m"
    assert candle.open == 100.0
    assert candle.high == 110.0
    assert candle.low == 90.0
    assert candle.close == 105.0
    assert candle.volume == 10.0
    assert candle.start_time.tzinfo is UTC


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"high": 80, "low": 90}, "high must be greater"),
        ({"open": 120}, "open must be within"),
        ({"close": 120}, "close must be within"),
        ({"volume": -1}, "volume must be greater"),
    ],
)
def test_direct_invalid_candle_is_rejected(
    changes: dict[str, object],
    message: str,
) -> None:
    kwargs: dict[str, object] = {
        "symbol": "BTCUSDT",
        "timeframe": "1m",
        "open": 100,
        "high": 110,
        "low": 90,
        "close": 105,
        "volume": 10,
        "start_time": datetime(2026, 1, 1, tzinfo=UTC),
    }
    kwargs.update(changes)

    with pytest.raises(
        ValueError,
        match=message,
    ):
        Candle(**kwargs)  # type: ignore[arg-type]


def test_concurrent_updates_do_not_lose_volume() -> None:
    builder = CandleBuilder()
    worker_count = 8
    updates_per_worker = 250

    def worker() -> None:
        for _ in range(updates_per_worker):
            builder.update(
                "BTCUSDT",
                "1m",
                100,
                1,
            )

    threads = [
        Thread(target=worker)
        for _ in range(worker_count)
    ]

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join()

    candle = builder.latest("BTCUSDT", "1m")

    assert candle is not None
    assert candle.volume == float(
        worker_count * updates_per_worker
    )
    assert builder.size == 1