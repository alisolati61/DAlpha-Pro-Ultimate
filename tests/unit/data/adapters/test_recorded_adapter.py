"""Behavioral tests for deterministic recorded exchange replay."""

from __future__ import annotations

from datetime import UTC, datetime
from threading import Thread

import pytest

from src.data.adapters.errors import (
    RecordedAdapterUnavailableError,
    RecordedReplayError,
    ReplaySequenceError,
)
from src.data.adapters.models import (
    RecordedMarketDataPayload,
    RecordedPayloadKind,
)
from src.data.adapters.recorded import (
    RECORDED_MARKET_DATA_ADAPTER_ID,
    RecordedExchangeMarketDataAdapter,
)
from src.data.service import MARKET_DATA_SERVICE_ID, MarketDataService


def recorded(
    sequence: int,
    kind: RecordedPayloadKind,
    payload: dict[str, object],
) -> RecordedMarketDataPayload:
    return RecordedMarketDataPayload.from_mapping(
        sequence=sequence,
        kind=kind,
        payload=payload,
    )


def snapshot_payload(sequence: int, price: float = 100):
    return recorded(
        sequence,
        RecordedPayloadKind.SNAPSHOT,
        {
            "symbol": "BTCUSDT",
            "exchange": "recorded",
            "timeframe": "1m",
            "price": price,
            "bid": price - 1,
            "ask": price + 1,
            "volume": 2,
            "timestamp": "2026-01-01T00:00:00Z",
        },
    )


def candle_payload(sequence: int):
    return recorded(
        sequence,
        RecordedPayloadKind.CANDLES,
        {
            "symbol": "BTCUSDT",
            "timeframe": "1h",
            "candles": [
                [1, 100, 110, 90, 105, 10, {"source": "recorded"}]
            ],
        },
    )


def order_book_payload(sequence: int):
    return recorded(
        sequence,
        RecordedPayloadKind.ORDER_BOOK,
        {
            "symbol": "BTCUSDT",
            "bids": [[99, 1], [100, 2]],
            "asks": [[102, 1], [101, 2]],
        },
    )


def running_adapter(
    payloads: tuple[RecordedMarketDataPayload, ...] = (),
) -> tuple[MarketDataService, RecordedExchangeMarketDataAdapter]:
    service = MarketDataService()
    service.initialize()
    service.start()
    adapter = RecordedExchangeMarketDataAdapter(service, payloads)
    adapter.initialize()
    adapter.start()
    return service, adapter


def test_explicit_lifecycle_and_service_definition() -> None:
    service = MarketDataService()
    adapter = RecordedExchangeMarketDataAdapter(service)

    with pytest.raises(RecordedAdapterUnavailableError):
        adapter.replay(())

    service.initialize()
    service.start()
    adapter.initialize()
    adapter.start()
    definition = adapter.definition()

    assert definition.service_id == RECORDED_MARKET_DATA_ADAPTER_ID
    assert definition.service is adapter
    assert definition.dependencies == (MARKET_DATA_SERVICE_ID,)

    adapter.stop()
    with pytest.raises(RecordedAdapterUnavailableError):
        adapter.replay(())


def test_all_recorded_kinds_replay_into_canonical_service() -> None:
    payloads = (
        snapshot_payload(1),
        candle_payload(2),
        order_book_payload(3),
    )
    service, adapter = running_adapter(payloads)

    result = adapter.replay()

    assert result.applied == 3
    assert result.last_sequence == 3
    assert result.digests == tuple(item.digest for item in payloads)
    latest = service.latest_snapshot("BTCUSDT", "recorded", "1m")
    assert latest is not None
    assert latest.timestamp == datetime(2026, 1, 1, tzinfo=UTC)
    packet = service.data_manager.get("BTCUSDT", "1h")
    assert packet is not None
    assert packet.candles[0][6] == {"source": "recorded"}
    assert service.order_book_manager.best_bid("BTCUSDT") == (
        100.0,
        2.0,
    )


def test_duplicate_replay_and_out_of_order_batches_fail_closed() -> None:
    service, adapter = running_adapter()
    first = snapshot_payload(1)

    assert adapter.replay((first,)).applied == 1

    with pytest.raises(ReplaySequenceError):
        adapter.replay((first,))
    with pytest.raises(ReplaySequenceError):
        adapter.replay((snapshot_payload(3), snapshot_payload(2)))

    assert adapter.last_sequence == 1
    assert service.snapshot_count == 1


def test_complete_batch_is_validated_before_first_ingestion() -> None:
    service, adapter = running_adapter()
    valid = snapshot_payload(1)
    invalid = recorded(
        2,
        RecordedPayloadKind.SNAPSHOT,
        {"unexpected": "field"},
    )

    from src.data.adapters.errors import InvalidRecordedPayloadError

    with pytest.raises(InvalidRecordedPayloadError):
        adapter.replay((valid, invalid))

    assert service.snapshot_count == 0
    assert adapter.last_sequence is None


class FailingMarketDataService(MarketDataService):
    fail_price = 200

    def ingest_snapshot(self, snapshot):  # type: ignore[no-untyped-def]
        if snapshot.price == self.fail_price:
            raise RuntimeError("api_key=hidden C:\\private\\recording")
        return super().ingest_snapshot(snapshot)


def test_cursor_advances_only_after_each_successful_event() -> None:
    service = FailingMarketDataService()
    service.initialize()
    service.start()
    adapter = RecordedExchangeMarketDataAdapter(service)
    adapter.initialize()
    adapter.start()

    with pytest.raises(RecordedReplayError) as captured:
        adapter.replay(
            (
                snapshot_payload(1, 100),
                snapshot_payload(2, 200),
            )
        )

    assert adapter.last_sequence == 1
    assert service.snapshot_count == 1
    assert "hidden" not in str(captured.value)

    service.fail_price = -1
    result = adapter.replay((snapshot_payload(2, 200),))
    assert result.last_sequence == 2
    assert service.snapshot_count == 2


def test_concurrent_duplicate_replay_applies_event_once() -> None:
    service, adapter = running_adapter()
    item = snapshot_payload(1)
    outcomes: list[str] = []

    def worker() -> None:
        try:
            adapter.replay((item,))
        except ReplaySequenceError:
            outcomes.append("duplicate")
        else:
            outcomes.append("applied")

    threads = [Thread(target=worker) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert outcomes.count("applied") == 1
    assert outcomes.count("duplicate") == 7
    assert service.snapshot_count == 1


@pytest.mark.parametrize(
    ("kind", "payload"),
    [
        (RecordedPayloadKind.SNAPSHOT, {"symbol": "BTCUSDT"}),
        (
            RecordedPayloadKind.CANDLES,
            {"symbol": "BTCUSDT", "timeframe": "1h", "candles": []},
        ),
        (
            RecordedPayloadKind.ORDER_BOOK,
            {"symbol": "BTCUSDT", "bids": "bad", "asks": []},
        ),
    ],
)
def test_invalid_schemas_do_not_mutate_target(
    kind: RecordedPayloadKind,
    payload: dict[str, object],
) -> None:
    from src.data.adapters.errors import InvalidRecordedPayloadError

    service, adapter = running_adapter()
    with pytest.raises(InvalidRecordedPayloadError):
        adapter.replay((recorded(1, kind, payload),))

    assert service.snapshot_count == 0
    assert service.candle_batch_count == 0
    assert service.order_book_count == 0
