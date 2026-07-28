"""Local lifecycle wrapper for the canonical deterministic strategy."""

from __future__ import annotations

from src.core.lifecycle.service import Service
from src.core.services.models import ServiceDefinition
from src.data.service import MARKET_DATA_SERVICE_ID
from src.strategy.market_structure import MarketStructureStrategy
from src.strategy.models import TradeProposal

STRATEGY_SERVICE_ID = "strategy"


class StrategyService(Service):
    def __init__(self, strategy: MarketStructureStrategy) -> None:
        self.strategy = strategy
        self._running = False

    def initialize(self) -> None:
        if not isinstance(self.strategy, MarketStructureStrategy):
            raise TypeError("strategy is invalid")

    def start(self) -> None:
        self._running = True

    def stop(self) -> None:
        self._running = False

    def definition(self) -> ServiceDefinition:
        return ServiceDefinition(
            STRATEGY_SERVICE_ID, self, (MARKET_DATA_SERVICE_ID,)
        )

    def evaluate(self, *, symbol: str, exchange: str, timeframe: str) -> TradeProposal:
        if not self._running:
            raise RuntimeError("Strategy service is unavailable.")
        return self.strategy.evaluate(
            symbol=symbol, exchange=exchange, timeframe=timeframe
        )


__all__ = ("STRATEGY_SERVICE_ID", "StrategyService")
