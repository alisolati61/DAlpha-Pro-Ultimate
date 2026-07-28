"""Unit tests for the synchronous canonical Market Data service."""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from threading import Thread

import pytest

from src.data.candle_builder import CandleBuilder
from src.data.data_manager import DataManager, DataPacket
from src.data.errors import (
    DataServiceUnavailableError,
    IngestionTransactionError,
    InvalidDataPacketError,
)
from src.data.market_data import MarketData
from src.data.orderbook_manager import OrderBookManager
from src.data.service import MARKET_DATA_SERVICE_ID, MarketDataService


def snapshot(
    *,
    price: float = 100,
    volume: float = 2,
) -> MarketData:
    return MarketData(
        symbol="BTCUSDT",
        exchange="local",
        timeframe="1m",
        price=price,
        bid=price - 1,
        ask=price + 1,
        volume=volume,
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
    )


def running_service(**kwargs: object) -> MarketDataService:
    service = MarketDataService(**kwargs)  # type: ignore[arg-type]
    service.initialize()
    service.start()
    return service


def test_explicit_lifecycle_and_definition() -> None:
    service = MarketDataService()

    with pytest.raises(DataServiceUnavailableError):
        service.ingest_snapshot(snapshot())

    service.initialize()
    service.start()
    assert service.ingest_snapshot(snapshot()) == snapshot()
    assert service.definition().service_id == MARKET_DATA_SERVICE_ID
    assert service.definition().service is service

    service.stop()
    with pytest.raises(DataServiceUnavailableError):
        service.ingest_snapshot(snapshot())


def test_snapshot_updates_tick_candle_cache_and_latest() -> None:
    service = running_service()
    accepted = service.ingest_snapshot(snapshot())
    key = service.snapshot_cache_key("BTCUSDT", "local", "1m")

    tick = service.tick_processor.latest("BTCUSDT")
    candle = service.candle_builder.latest("BTCUSDT", "1m")
    assert tick is not None and tick.price == 100
    assert candle is not None and candle.close == 100
    assert service.data_cache.get(key) is accepted
    assert service.latest_snapshot("BTCUSDT", "local", "1m") is accepted
    assert service.snapshot_count == 1


def test_repeated_snapshots_preserve_ohlcv_semantics() -> None:
    service = running_service()
    service.ingest_snapshot(snapshot(price=100, volume=2))
    service.ingest_snapshot(snapshot(price=110, volume=3))
    service.ingest_snapshot(snapshot(price=90, volume=4))

    candle = service.candle_builder.latest("BTCUSDT", "1m")
    assert candle is not None
    assert (
        candle.open,
        candle.high,
        candle.low,
        candle.close,
        candle.volume,
    ) == (100, 110, 90, 90, 9)
    assert service.snapshot_count == 3


def test_invalid_snapshot_leaves_every_component_unchanged() -> None:
    service = running_service()
    accepted = service.ingest_snapshot(snapshot())
    tick = service.tick_processor.latest("BTCUSDT")
    candle = service.candle_builder.latest("BTCUSDT", "1m")
    key = service.snapshot_cache_key("BTCUSDT", "local", "1m")

    with pytest.raises(InvalidDataPacketError):
        service.ingest_snapshot({"price": 200})  # type: ignore[arg-type]

    assert service.tick_processor.latest("BTCUSDT") is tick
    assert service.candle_builder.latest("BTCUSDT", "1m") is candle
    assert service.data_cache.get(key) is accepted
    assert service.snapshot_count == 1


def test_raw_candles_are_validated_and_mutation_isolated() -> None:
    service = running_service()
    extra = {"source": "local"}
    packet = DataPacket(
        "BTCUSDT",
        "1h",
        [[1, 100, 110, 90, 105, 10, extra]],
    )

    accepted = service.ingest_candles(packet)
    packet.candles[0][1] = 999
    extra["source"] = "changed"
    accepted.candles[0][1] = 888

    stored = service.data_manager.get("BTCUSDT", "1h")
    assert stored is not None
    assert stored.candles[0][1] == 100
    assert stored.candles[0][6] == {"source": "local"}
    assert service.candle_batch_count == 1

    with pytest.raises(InvalidDataPacketError):
        service.ingest_candles({"candles": []})  # type: ignore[arg-type]
    assert service.data_manager.size == 1
    assert service.candle_batch_count == 1


def test_order_book_ingestion_delegates_to_manager() -> None:
    service = running_service()

    book = service.ingest_order_book(
        "BTCUSDT",
        [(99, 1), (100, 2)],
        [(102, 1), (101, 2)],
    )

    assert book.bids[0] == (100.0, 2.0)
    assert book.asks[0] == (101.0, 2.0)
    assert service.order_book_manager.best_bid("BTCUSDT") == (
        100.0,
        2.0,
    )
    assert service.order_book_count == 1


class FailingCandleBuilder(CandleBuilder):
    fail = False

    def update(self, *args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        result = super().update(*args, **kwargs)  # type: ignore[arg-type]
        if self.fail:
            raise RuntimeError("api_key=hidden C:\\private\\failure")
        return result


class FailingDataManager(DataManager):
    fail = False

    def update(self, packet: DataPacket) -> DataPacket:
        result = super().update(packet)
        if self.fail:
            raise RuntimeError("password=hidden")
        return result


class FailingOrderBookManager(OrderBookManager):
    fail = False

    def update(self, *args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        result = super().update(*args, **kwargs)  # type: ignore[arg-type]
        if self.fail:
            raise RuntimeError("secret=hidden")
        return result


def test_snapshot_failure_restores_all_components_and_counter() -> None:
    builder = FailingCandleBuilder()
    service = running_service(candle_builder=builder)
    first = service.ingest_snapshot(snapshot())
    tick = service.tick_processor.latest("BTCUSDT")
    candle = builder.latest("BTCUSDT", "1m")
    key = service.snapshot_cache_key("BTCUSDT", "local", "1m")
    builder.fail = True

    with pytest.raises(IngestionTransactionError) as captured:
        service.ingest_snapshot(snapshot(price=200))

    assert "hidden" not in str(captured.value)
    assert service.tick_processor.latest("BTCUSDT") is tick
    assert builder.latest("BTCUSDT", "1m") is candle
    assert candle is not None and candle.close == 100
    assert service.data_cache.get(key) is first
    assert service.latest_snapshot("BTCUSDT", "local", "1m") is first
    assert service.snapshot_count == 1


def test_candle_and_order_failures_restore_storage_and_counters() -> None:
    manager = FailingDataManager()
    books = FailingOrderBookManager()
    service = running_service(
        data_manager=manager,
        order_book_manager=books,
    )
    first_packet = DataPacket(
        "BTCUSDT",
        "1h",
        [[1, 100, 110, 90, 105, 10]],
    )
    service.ingest_candles(first_packet)
    service.ingest_order_book("BTCUSDT", [(100, 1)], [(101, 1)])
    manager.fail = True
    books.fail = True

    with pytest.raises(IngestionTransactionError):
        service.ingest_candles(
            DataPacket(
                "BTCUSDT",
                "1h",
                [[2, 200, 210, 190, 205, 10]],
            )
        )
    with pytest.raises(IngestionTransactionError):
        service.ingest_order_book(
            "BTCUSDT",
            [(200, 1)],
            [(201, 1)],
        )

    stored = service.data_manager.get("BTCUSDT", "1h")
    assert stored is not None and stored.candles[0][1] == 100
    assert service.order_book_manager.best_bid("BTCUSDT") == (100.0, 1.0)
    assert service.candle_batch_count == 1
    assert service.order_book_count == 1


def test_stop_clears_all_runtime_owned_data() -> None:
    service = running_service()
    service.ingest_snapshot(snapshot())
    service.ingest_candles(
        DataPacket(
            "BTCUSDT",
            "1h",
            [[1, 100, 110, 90, 105, 10]],
        )
    )
    service.ingest_order_book("BTCUSDT", [(100, 1)], [(101, 1)])

    service.stop()

    assert service.tick_processor.processed_ticks == 0
    assert service.candle_builder.size == 0
    assert service.order_book_manager.size == 0
    assert service.data_cache.size == 0
    assert service.data_manager.size == 0
    assert service.snapshot_count == 0


def test_concurrent_snapshot_ingestion_is_serialized() -> None:
    service = running_service()

    def worker() -> None:
        for _ in range(100):
            service.ingest_snapshot(snapshot(volume=1))

    threads = [Thread(target=worker) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    candle = service.candle_builder.latest("BTCUSDT", "1m")
    assert service.snapshot_count == 800
    assert service.tick_processor.processed_ticks == 800
    assert candle is not None and candle.volume == 800


def test_import_and_construction_have_no_external_side_effects(
    tmp_path: Path,
) -> None:
    project_root = Path(__file__).resolve().parents[3]
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(project_root)
    environment["BINGX_API_KEY"] = "must-not-be-read"
    script = (
        "import sys;"
        "from src.data.service import MarketDataService;"
        "service=MarketDataService();service.initialize();"
        "blocked=('src.config.settings','src.logger.logger',"
        "'src.exchange','src.execution.execution_engine');"
        "assert not any(name in sys.modules for name in blocked)"
    )

    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert tuple(tmp_path.iterdir()) == ()
