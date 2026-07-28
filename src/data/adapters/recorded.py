"""Local recorded exchange payload adapter with no transport behavior."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from threading import RLock
from typing import Any, TypeAlias

from src.core.lifecycle.service import Service
from src.core.services.models import ServiceDefinition
from src.data.adapters.errors import (
    InvalidRecordedPayloadError,
    RecordedAdapterUnavailableError,
    RecordedReplayError,
    ReplaySequenceError,
)
from src.data.adapters.models import (
    RecordedMarketDataPayload,
    RecordedPayloadKind,
    ReplayResult,
)
from src.data.data_manager import DataPacket
from src.data.market_data import MarketData
from src.data.service import MARKET_DATA_SERVICE_ID, MarketDataService

RECORDED_MARKET_DATA_ADAPTER_ID = (
    "recorded-exchange-market-data-adapter"
)

_PreparedEvent: TypeAlias = tuple[
    RecordedMarketDataPayload,
    MarketData | DataPacket | tuple[str, list[Any], list[Any]],
]


class RecordedExchangeMarketDataAdapter(Service):
    """Replay immutable recorded payloads into an explicit local Data service."""

    def __init__(
        self,
        market_data_service: MarketDataService,
        payloads: Iterable[RecordedMarketDataPayload] = (),
    ) -> None:
        self.market_data_service = market_data_service
        self.payloads = tuple(payloads)
        self._accepting = False
        self._last_sequence: int | None = None
        self._lock = RLock()

    def initialize(self) -> None:
        if not isinstance(self.market_data_service, MarketDataService):
            raise InvalidRecordedPayloadError
        self._prepare(self.payloads, previous_sequence=None)

    def start(self) -> None:
        with self._lock:
            self._accepting = True

    def stop(self) -> None:
        with self._lock:
            self._accepting = False
            self._last_sequence = None

    def definition(self) -> ServiceDefinition:
        """Declare the explicit dependency on the canonical Data service."""

        return ServiceDefinition(
            RECORDED_MARKET_DATA_ADAPTER_ID,
            self,
            (MARKET_DATA_SERVICE_ID,),
        )

    def replay(
        self,
        payloads: Iterable[RecordedMarketDataPayload] | None = None,
    ) -> ReplayResult:
        """Validate the complete batch, then ingest in strict sequence order.

        The cursor advances only after each accepted event. If ingestion fails,
        already accepted events remain committed and callers can safely resume
        with events after ``last_sequence``.
        """

        with self._lock:
            if not self._accepting:
                raise RecordedAdapterUnavailableError
            selected = self.payloads if payloads is None else tuple(payloads)
            prepared = self._prepare(
                selected,
                previous_sequence=self._last_sequence,
            )
            digests: list[str] = []

            for payload, command in prepared:
                try:
                    self._apply(payload.kind, command)
                except Exception as error:
                    raise RecordedReplayError from error
                self._last_sequence = payload.sequence
                digests.append(payload.digest)

            return ReplayResult(
                applied=len(digests),
                last_sequence=self._last_sequence,
                digests=tuple(digests),
            )

    @property
    def last_sequence(self) -> int | None:
        with self._lock:
            return self._last_sequence

    def _prepare(
        self,
        payloads: tuple[RecordedMarketDataPayload, ...],
        *,
        previous_sequence: int | None,
    ) -> tuple[_PreparedEvent, ...]:
        prepared: list[_PreparedEvent] = []
        last = previous_sequence
        for payload in payloads:
            if not isinstance(payload, RecordedMarketDataPayload):
                raise InvalidRecordedPayloadError
            if last is not None and payload.sequence <= last:
                raise ReplaySequenceError
            command = self._command(payload)
            prepared.append((payload, command))
            last = payload.sequence
        return tuple(prepared)

    @staticmethod
    def _command(
        payload: RecordedMarketDataPayload,
    ) -> MarketData | DataPacket | tuple[str, list[Any], list[Any]]:
        values = payload.to_mapping()
        try:
            if payload.kind is RecordedPayloadKind.SNAPSHOT:
                expected = {
                    "symbol",
                    "exchange",
                    "timeframe",
                    "price",
                    "bid",
                    "ask",
                    "volume",
                    "timestamp",
                }
                if set(values) != expected:
                    raise InvalidRecordedPayloadError
                timestamp = values["timestamp"]
                if not isinstance(timestamp, str):
                    raise InvalidRecordedPayloadError
                parsed_timestamp = datetime.fromisoformat(
                    timestamp.replace("Z", "+00:00")
                )
                if (
                    parsed_timestamp.tzinfo is None
                    or parsed_timestamp.utcoffset() is None
                ):
                    raise InvalidRecordedPayloadError
                return MarketData(
                    symbol=values["symbol"],
                    exchange=values["exchange"],
                    timeframe=values["timeframe"],
                    price=values["price"],
                    bid=values["bid"],
                    ask=values["ask"],
                    volume=values["volume"],
                    timestamp=parsed_timestamp,
                )

            if payload.kind is RecordedPayloadKind.CANDLES:
                if set(values) != {"symbol", "timeframe", "candles"}:
                    raise InvalidRecordedPayloadError
                return DataPacket(
                    symbol=values["symbol"],
                    timeframe=values["timeframe"],
                    candles=values["candles"],
                )

            if payload.kind is RecordedPayloadKind.ORDER_BOOK:
                if set(values) != {"symbol", "bids", "asks"}:
                    raise InvalidRecordedPayloadError
                symbol = values["symbol"]
                bids = values["bids"]
                asks = values["asks"]
                if (
                    not isinstance(symbol, str)
                    or not isinstance(bids, list)
                    or not isinstance(asks, list)
                ):
                    raise InvalidRecordedPayloadError
                return (symbol, bids, asks)
        except InvalidRecordedPayloadError:
            raise
        except Exception as error:
            raise InvalidRecordedPayloadError from error
        raise InvalidRecordedPayloadError

    def _apply(
        self,
        kind: RecordedPayloadKind,
        command: MarketData | DataPacket | tuple[str, list[Any], list[Any]],
    ) -> None:
        if kind is RecordedPayloadKind.SNAPSHOT:
            if not isinstance(command, MarketData):
                raise InvalidRecordedPayloadError
            self.market_data_service.ingest_snapshot(command)
            return
        if kind is RecordedPayloadKind.CANDLES:
            if not isinstance(command, DataPacket):
                raise InvalidRecordedPayloadError
            self.market_data_service.ingest_candles(command)
            return
        if (
            kind is RecordedPayloadKind.ORDER_BOOK
            and isinstance(command, tuple)
        ):
            self.market_data_service.ingest_order_book(*command)
            return
        raise InvalidRecordedPayloadError


__all__ = (
    "RECORDED_MARKET_DATA_ADAPTER_ID",
    "RecordedExchangeMarketDataAdapter",
)
