from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(slots=True)
class Tick:

    symbol: str

    price: float

    volume: float

    timestamp: datetime


class TickProcessor:
    """
    Processes live market ticks.

    Responsibilities
    ----------------
    - Store latest tick
    - Count processed ticks
    - Provide latest market snapshot

    Future
    -------
    - Tick aggregation
    - VWAP
    - Delta Volume
    - Footprint Engine
    """

    def __init__(self) -> None:

        self._latest: dict[str, Tick] = {}

        self._count = 0

    # --------------------------------------------------

    def process(
        self,
        symbol: str,
        price: float,
        volume: float,
        timestamp: datetime | None = None,
    ) -> Tick:

        if timestamp is None:

            timestamp = datetime.now(UTC)

        tick = Tick(

            symbol=symbol,

            price=float(price),

            volume=float(volume),

            timestamp=timestamp,

        )

        self._latest[symbol] = tick

        self._count += 1

        return tick

    # --------------------------------------------------

    def latest(
        self,
        symbol: str,
    ) -> Tick | None:

        return self._latest.get(symbol)

    # --------------------------------------------------

    @property
    def processed_ticks(self) -> int:

        return self._count

    # --------------------------------------------------

    def clear(self) -> None:

        self._latest.clear()

        self._count = 0