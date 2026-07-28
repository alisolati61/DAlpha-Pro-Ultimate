"""Behavioral and compatibility tests for live tick processing."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from threading import Thread

import pytest

from src.data.tick_processor import (
    Tick,
    TickProcessor,
)


def test_process_preserves_public_contract() -> None:
    processor = TickProcessor()

    tick = processor.process(
        symbol="BTCUSDT",
        price=100,
        volume=5,
    )

    assert isinstance(tick, Tick)
    assert tick.symbol == "BTCUSDT"
    assert tick.price == 100.0
    assert tick.volume == 5.0
    assert tick.timestamp.tzinfo is UTC


def test_latest_returns_last_tick_for_symbol() -> None:
    processor = TickProcessor()
    first = processor.process("BTCUSDT", 100, 5)
    second = processor.process("BTCUSDT", 101, 6)

    assert first is not second
    assert processor.latest("BTCUSDT") is second
    assert processor.latest("BTCUSDT").price == 101.0


def test_processed_counter_counts_accepted_ticks() -> None:
    processor = TickProcessor()

    processor.process("BTCUSDT", 1, 1)
    processor.process("BTCUSDT", 2, 1)

    assert processor.processed_ticks == 2


def test_clear_preserves_legacy_behavior() -> None:
    processor = TickProcessor()
    processor.process("BTCUSDT", 1, 1)
    processor.process("ETHUSDT", 2, 1)

    processor.clear()

    assert processor.processed_ticks == 0
    assert processor.latest("BTCUSDT") is None
    assert processor.latest("ETHUSDT") is None


def test_multiple_symbols_keep_independent_latest_ticks() -> None:
    processor = TickProcessor()

    btc = processor.process("BTCUSDT", 100, 1)
    eth = processor.process("ETHUSDT", 50, 2)

    assert processor.latest("BTCUSDT") is btc
    assert processor.latest("ETHUSDT") is eth


def test_symbol_is_trimmed_for_process_and_latest() -> None:
    processor = TickProcessor()

    tick = processor.process(" BTCUSDT ", 100, 1)

    assert tick.symbol == "BTCUSDT"
    assert processor.latest(" BTCUSDT ") is tick


def test_symbol_keys_remain_case_sensitive() -> None:
    processor = TickProcessor()

    upper = processor.process("BTCUSDT", 100, 1)
    lower = processor.process("btcusdt", 101, 1)

    assert processor.latest("BTCUSDT") is upper
    assert processor.latest("btcusdt") is lower
    assert processor.processed_ticks == 2


def test_naive_timestamp_is_interpreted_as_utc() -> None:
    timestamp = datetime(2026, 1, 1, 12, 30)

    tick = TickProcessor().process(
        "BTCUSDT",
        100,
        1,
        timestamp,
    )

    assert tick.timestamp == timestamp.replace(tzinfo=UTC)
    assert tick.timestamp.tzinfo is UTC


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

    tick = TickProcessor().process(
        "BTCUSDT",
        100,
        1,
        timestamp,
    )

    assert tick.timestamp == datetime(
        2026,
        1,
        1,
        9,
        0,
        tzinfo=UTC,
    )
    assert tick.timestamp.tzinfo is UTC


def test_older_timestamp_still_replaces_latest_for_compatibility() -> None:
    processor = TickProcessor()
    newer = datetime(2026, 1, 2, tzinfo=UTC)
    older = datetime(2026, 1, 1, tzinfo=UTC)

    processor.process("BTCUSDT", 100, 1, newer)
    older_tick = processor.process(
        "BTCUSDT",
        99,
        1,
        older,
    )

    assert processor.latest("BTCUSDT") is older_tick
    assert processor.processed_ticks == 2


@pytest.mark.parametrize(
    ("symbol", "message"),
    [
        ("", "symbol cannot be empty"),
        ("   ", "symbol cannot be empty"),
        (123, "symbol must be a string"),
        (None, "symbol must be a string"),
    ],
)
def test_invalid_symbol_is_rejected(
    symbol: object,
    message: str,
) -> None:
    processor = TickProcessor()

    with pytest.raises(
        (TypeError, ValueError),
        match=message,
    ):
        processor.process(
            symbol,  # type: ignore[arg-type]
            100,
            1,
        )

    assert processor.processed_ticks == 0


@pytest.mark.parametrize(
    ("field_name", "value", "message"),
    [
        ("price", 0, "price must be greater than zero"),
        ("price", -1, "price must be greater than zero"),
        ("price", True, "price must be numeric"),
        ("price", "bad", "price must be numeric"),
        ("price", None, "price must be numeric"),
        ("price", float("nan"), "price must be finite"),
        ("price", float("inf"), "price must be finite"),
        ("volume", -1, "volume must be greater than or equal"),
        ("volume", True, "volume must be numeric"),
        ("volume", "bad", "volume must be numeric"),
        ("volume", None, "volume must be numeric"),
        ("volume", float("nan"), "volume must be finite"),
        ("volume", float("inf"), "volume must be finite"),
    ],
)
def test_invalid_numeric_values_are_rejected_atomically(
    field_name: str,
    value: object,
    message: str,
) -> None:
    processor = TickProcessor()
    original = processor.process("BTCUSDT", 100, 1)

    kwargs: dict[str, object] = {
        "symbol": "BTCUSDT",
        "price": 101,
        "volume": 2,
    }
    kwargs[field_name] = value

    with pytest.raises(
        (TypeError, ValueError),
        match=message,
    ):
        processor.process(**kwargs)  # type: ignore[arg-type]

    assert processor.latest("BTCUSDT") is original
    assert processor.processed_ticks == 1


def test_zero_volume_is_valid() -> None:
    tick = TickProcessor().process(
        "BTCUSDT",
        100,
        0,
    )

    assert tick.volume == 0.0


def test_timestamp_must_be_datetime() -> None:
    processor = TickProcessor()

    with pytest.raises(
        TypeError,
        match="timestamp must be a datetime",
    ):
        processor.process(
            "BTCUSDT",
            100,
            1,
            timestamp=1_700_000_000,  # type: ignore[arg-type]
        )

    assert processor.processed_ticks == 0


def test_direct_tick_construction_is_normalized() -> None:
    tick = Tick(
        symbol=" BTCUSDT ",
        price="100",  # type: ignore[arg-type]
        volume="5",  # type: ignore[arg-type]
        timestamp=datetime(2026, 1, 1),
    )

    assert tick.symbol == "BTCUSDT"
    assert tick.price == 100.0
    assert tick.volume == 5.0
    assert tick.timestamp.tzinfo is UTC


def test_tick_remains_mutable_for_backward_compatibility() -> None:
    tick = TickProcessor().process(
        "BTCUSDT",
        100,
        1,
    )

    tick.price = 101.0

    assert tick.price == 101.0


def test_latest_rejects_invalid_lookup_without_state_change() -> None:
    processor = TickProcessor()
    original = processor.process("BTCUSDT", 100, 1)

    with pytest.raises(ValueError, match="symbol cannot be empty"):
        processor.latest("   ")

    assert processor.latest("BTCUSDT") is original
    assert processor.processed_ticks == 1


def test_concurrent_processing_does_not_lose_count() -> None:
    processor = TickProcessor()
    worker_count = 8
    ticks_per_worker = 250

    def worker(worker_id: int) -> None:
        for index in range(ticks_per_worker):
            processor.process(
                f"SYMBOL-{worker_id}",
                index + 1,
                1,
            )

    threads = [
        Thread(target=worker, args=(worker_id,))
        for worker_id in range(worker_count)
    ]

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join()

    assert processor.processed_ticks == (
        worker_count * ticks_per_worker
    )

    for worker_id in range(worker_count):
        tick = processor.latest(f"SYMBOL-{worker_id}")
        assert tick is not None
        assert tick.price == float(ticks_per_worker)


def test_clear_after_processing_resets_all_state() -> None:
    processor = TickProcessor()

    for index in range(10):
        processor.process(
            f"SYMBOL-{index}",
            index + 1,
            index,
        )

    processor.clear()

    assert processor.processed_ticks == 0

    for index in range(10):
        assert processor.latest(f"SYMBOL-{index}") is None


def test_private_transaction_restore_preserves_previous_identity() -> None:
    processor = TickProcessor()
    original = processor.process("BTCUSDT", 100, 1)
    state = processor._snapshot_state()
    processor.process("BTCUSDT", 200, 2)

    processor._restore_state(state)

    assert processor.latest("BTCUSDT") is original
    assert processor.processed_ticks == 1
