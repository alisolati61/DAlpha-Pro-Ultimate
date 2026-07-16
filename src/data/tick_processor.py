from __future__ import annotations

from src.domain.market_data import MarketData


class TickProcessor:
    """
    Processes validated market ticks.
    """

    def __init__(self):

        self._last_tick: MarketData | None = None

    def process(
        self,
        tick: MarketData,
    ) -> MarketData:

        self._last_tick = tick

        return tick

    @property
    def last_tick(self) -> MarketData | None:

        return self._last_tick