"""Validated, mutation-isolated storage for raw OHLCV batches."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from threading import RLock
from typing import Any, TypeAlias

from src.data.data_validator import DataValidator
from src.data.errors import InvalidDataPacketError

CandleRows: TypeAlias = list[list[Any]]
_StoredPacket: TypeAlias = tuple[str, str, CandleRows]


def _key_text(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InvalidDataPacketError
    return value.strip()


@dataclass(slots=True)
class DataPacket:
    """Validated raw candle batch with caller-owned mutable output."""

    symbol: str
    timeframe: str
    candles: CandleRows

    def __post_init__(self) -> None:
        symbol = _key_text(self.symbol)
        timeframe = _key_text(self.timeframe)
        try:
            candles = deepcopy(self.candles)
        except Exception as error:
            raise InvalidDataPacketError from error
        result = DataValidator().validate(candles)
        if not result.valid:
            raise InvalidDataPacketError
        self.symbol = symbol
        self.timeframe = timeframe
        self.candles = candles


class DataManager:
    """Atomically replace and defensively return candle batches."""

    def __init__(self) -> None:
        self._storage: dict[tuple[str, str], _StoredPacket] = {}
        self._lock = RLock()

    def update(self, packet: DataPacket) -> DataPacket:
        if not isinstance(packet, DataPacket):
            raise InvalidDataPacketError
        try:
            candles = deepcopy(packet.candles)
        except Exception as error:
            raise InvalidDataPacketError from error
        if not DataValidator().validate(candles).valid:
            raise InvalidDataPacketError
        stored: _StoredPacket = (
            packet.symbol,
            packet.timeframe,
            candles,
        )
        key = (stored[0], stored[1])
        with self._lock:
            self._storage[key] = stored
        return self._public(stored)

    def get(
        self,
        symbol: str,
        timeframe: str,
    ) -> DataPacket | None:
        key = (_key_text(symbol), _key_text(timeframe))
        with self._lock:
            stored = self._storage.get(key)
            return None if stored is None else self._public(stored)

    def clear(self) -> None:
        with self._lock:
            self._storage.clear()

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._storage)

    @staticmethod
    def _public(stored: _StoredPacket) -> DataPacket:
        return DataPacket(
            symbol=stored[0],
            timeframe=stored[1],
            candles=deepcopy(stored[2]),
        )

    def _snapshot_state(
        self,
    ) -> dict[tuple[str, str], _StoredPacket]:
        with self._lock:
            return deepcopy(self._storage)

    def _restore_state(
        self,
        state: dict[tuple[str, str], _StoredPacket],
    ) -> None:
        with self._lock:
            self._storage = deepcopy(state)


__all__ = (
    "CandleRows",
    "DataManager",
    "DataPacket",
)
