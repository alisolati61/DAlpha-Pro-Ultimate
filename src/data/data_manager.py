from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class DataPacket:
    """
    Standard market data container.
    """

    symbol: str
    timeframe: str
    candles: list[Any]


class DataManager:
    """
    Central data provider.

    Responsibilities
    ----------------
    - Receive market data
    - Cache data
    - Serve other engines

    Future
    -------
    - Redis Cache
    - Memory Cache
    - Historical Storage
    """

    def __init__(self) -> None:

        self._storage: dict[
            tuple[str, str],
            DataPacket,
        ] = {}

    # ------------------------------------------------

    def update(
        self,
        packet: DataPacket,
    ) -> None:

        key = (
            packet.symbol,
            packet.timeframe,
        )

        self._storage[key] = packet

    # ------------------------------------------------

    def get(
        self,
        symbol: str,
        timeframe: str,
    ) -> DataPacket | None:

        return self._storage.get(
            (
                symbol,
                timeframe,
            )
        )

    # ------------------------------------------------

    def clear(self) -> None:

        self._storage.clear()

    # ------------------------------------------------

    @property
    def size(self) -> int:

        return len(self._storage)