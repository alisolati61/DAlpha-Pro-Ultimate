"""Synchronous, local-only canonical Market Data runtime service."""

from __future__ import annotations

from collections.abc import Sequence
from threading import RLock
from typing import Any

from src.core.lifecycle.service import Service
from src.core.services.models import ServiceDefinition
from src.data.candle_builder import CandleBuilder
from src.data.data_cache import DataCache
from src.data.data_manager import DataManager, DataPacket
from src.data.data_validator import DataValidator
from src.data.errors import (
    DataServiceUnavailableError,
    IngestionTransactionError,
    InvalidDataPacketError,
)
from src.data.market_data import MarketData
from src.data.orderbook_manager import OrderBook, OrderBookManager
from src.data.tick_processor import TickProcessor

MARKET_DATA_SERVICE_ID = "market-data"


class MarketDataService(Service):
    """Own canonical local ingestion components without external I/O."""

    def __init__(
        self,
        *,
        tick_processor: TickProcessor | None = None,
        candle_builder: CandleBuilder | None = None,
        order_book_manager: OrderBookManager | None = None,
        data_cache: DataCache | None = None,
        data_manager: DataManager | None = None,
        data_validator: DataValidator | None = None,
    ) -> None:
        self.tick_processor = (
            tick_processor
            if tick_processor is not None
            else TickProcessor()
        )
        self.candle_builder = (
            candle_builder
            if candle_builder is not None
            else CandleBuilder()
        )
        self.order_book_manager = (
            order_book_manager
            if order_book_manager is not None
            else OrderBookManager()
        )
        self.data_cache = (
            data_cache
            if data_cache is not None
            else DataCache()
        )
        self.data_manager = (
            data_manager
            if data_manager is not None
            else DataManager()
        )
        self.data_validator = (
            data_validator
            if data_validator is not None
            else DataValidator()
        )
        self._accepting = False
        self._latest: dict[str, MarketData] = {}
        self._snapshot_count = 0
        self._candle_batch_count = 0
        self._order_book_count = 0
        self._lock = RLock()

    def initialize(self) -> None:
        """Validate local collaborators without performing lifecycle work."""

        expected = (
            (self.tick_processor, TickProcessor),
            (self.candle_builder, CandleBuilder),
            (self.order_book_manager, OrderBookManager),
            (self.data_cache, DataCache),
            (self.data_manager, DataManager),
            (self.data_validator, DataValidator),
        )
        if not all(isinstance(value, contract) for value, contract in expected):
            raise IngestionTransactionError

    def start(self) -> None:
        with self._lock:
            self._accepting = True

    def stop(self) -> None:
        with self._lock:
            self._accepting = False
            errors: list[BaseException] = []
            for clear in (
                self.tick_processor.clear,
                self.candle_builder.clear,
                self.order_book_manager.clear,
                self.data_cache.clear,
                self.data_manager.clear,
            ):
                try:
                    clear()
                except BaseException as error:
                    errors.append(error)
            self._latest.clear()
            self._snapshot_count = 0
            self._candle_batch_count = 0
            self._order_book_count = 0
            if errors:
                raise BaseExceptionGroup(
                    "Local market data cleanup failed.",
                    errors,
                )

    def definition(self) -> ServiceDefinition:
        """Return the explicit dependency-free runtime definition."""

        return ServiceDefinition(MARKET_DATA_SERVICE_ID, self)

    def ingest_snapshot(self, snapshot: MarketData) -> MarketData:
        """Atomically ingest one canonical immutable market snapshot."""

        if not isinstance(snapshot, MarketData):
            raise InvalidDataPacketError

        cache_key = self.snapshot_cache_key(
            snapshot.symbol,
            snapshot.exchange,
            snapshot.timeframe,
        )
        with self._lock:
            self._require_running()
            previous = self._snapshot_transaction_state()
            try:
                self.tick_processor.process(
                    snapshot.symbol,
                    snapshot.price,
                    snapshot.volume,
                    snapshot.timestamp,
                )
                self.candle_builder.update(
                    snapshot.symbol,
                    snapshot.timeframe,
                    snapshot.price,
                    snapshot.volume,
                    snapshot.timestamp,
                )
                self.data_cache.set(cache_key, snapshot)
                self._latest[cache_key] = snapshot
                self._snapshot_count += 1
            except BaseException as error:
                try:
                    self._restore_snapshot_transaction(previous)
                except BaseException:
                    raise IngestionTransactionError from error
                raise IngestionTransactionError from error
            return snapshot

    def ingest_candles(self, packet: DataPacket) -> DataPacket:
        """Validate and atomically store one raw OHLCV batch."""

        if not isinstance(packet, DataPacket):
            raise InvalidDataPacketError
        try:
            validation = self.data_validator.validate(packet.candles)
        except BaseException as error:
            raise IngestionTransactionError from error
        if not validation.valid:
            raise InvalidDataPacketError

        with self._lock:
            self._require_running()
            previous_state = self.data_manager._snapshot_state()
            previous_count = self._candle_batch_count
            try:
                accepted = self.data_manager.update(packet)
                self._candle_batch_count += 1
            except BaseException as error:
                try:
                    self.data_manager._restore_state(previous_state)
                except BaseException:
                    raise IngestionTransactionError from error
                self._candle_batch_count = previous_count
                raise IngestionTransactionError from error
            return accepted

    def ingest_order_book(
        self,
        symbol: str,
        bids: Sequence[Sequence[Any]],
        asks: Sequence[Sequence[Any]],
    ) -> OrderBook:
        """Validate first, then atomically replace one local order book."""

        prepared = self.order_book_manager.prepare(symbol, bids, asks)
        with self._lock:
            self._require_running()
            previous_state = self.order_book_manager._snapshot_state()
            previous_count = self._order_book_count
            try:
                accepted = self.order_book_manager.update(
                    prepared[0],
                    prepared[1],
                    prepared[2],
                )
                self._order_book_count += 1
            except BaseException as error:
                try:
                    self.order_book_manager._restore_state(previous_state)
                except BaseException:
                    raise IngestionTransactionError from error
                self._order_book_count = previous_count
                raise IngestionTransactionError from error
            return accepted

    def latest_snapshot(
        self,
        symbol: str,
        exchange: str,
        timeframe: str,
    ) -> MarketData | None:
        key = self.snapshot_cache_key(symbol, exchange, timeframe)
        with self._lock:
            return self._latest.get(key)

    @staticmethod
    def snapshot_cache_key(
        symbol: str,
        exchange: str,
        timeframe: str,
    ) -> str:
        values: list[str] = []
        for value in (exchange, symbol, timeframe):
            if not isinstance(value, str) or not value.strip():
                raise InvalidDataPacketError
            values.append(value.strip())
        return "market-data:" + ":".join(values)

    @property
    def snapshot_count(self) -> int:
        with self._lock:
            return self._snapshot_count

    @property
    def candle_batch_count(self) -> int:
        with self._lock:
            return self._candle_batch_count

    @property
    def order_book_count(self) -> int:
        with self._lock:
            return self._order_book_count

    def _require_running(self) -> None:
        if not self._accepting:
            raise DataServiceUnavailableError

    def _snapshot_transaction_state(self) -> tuple[
        object,
        object,
        object,
        dict[str, MarketData],
        int,
    ]:
        return (
            self.tick_processor._snapshot_state(),
            self.candle_builder._snapshot_state(),
            self.data_cache._snapshot_state(),
            dict(self._latest),
            self._snapshot_count,
        )

    def _restore_snapshot_transaction(
        self,
        state: tuple[
            object,
            object,
            object,
            dict[str, MarketData],
            int,
        ],
    ) -> None:
        self.tick_processor._restore_state(state[0])  # type: ignore[arg-type]
        self.candle_builder._restore_state(state[1])  # type: ignore[arg-type]
        self.data_cache._restore_state(state[2])  # type: ignore[arg-type]
        self._latest = dict(state[3])
        self._snapshot_count = state[4]


__all__ = (
    "MARKET_DATA_SERVICE_ID",
    "MarketDataService",
)
