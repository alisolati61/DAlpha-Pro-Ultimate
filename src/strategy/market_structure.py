"""One deterministic market-structure strategy over canonical candle state."""

from __future__ import annotations

from datetime import datetime

from src.analysis.smart_money.market_structure import MarketStructureEngine, Trend
from src.data.service import MarketDataService
from src.strategy.models import ProposalDirection, TradeProposal


class MarketStructureStrategy:
    strategy_id = "market-structure"
    strategy_version = "1.0.0"

    def __init__(self, market_data: MarketDataService) -> None:
        if not isinstance(market_data, MarketDataService):
            raise TypeError("market_data must be a MarketDataService")
        self._market_data = market_data
        self._engine = MarketStructureEngine()

    def evaluate(
        self, *, symbol: str, exchange: str, timeframe: str
    ) -> TradeProposal:
        packet = self._market_data.data_manager.get(symbol, timeframe)
        if packet is None:
            raise ValueError("Canonical candle state is unavailable.")
        candles = packet.candles
        last = candles[-1]
        timestamp = _timestamp(last[0])
        entry = round(float(last[4]), 8)
        structure = self._engine.analyze(
            (row[2] for row in candles), (row[3] for row in candles)
        )
        direction = {
            Trend.BULLISH: ProposalDirection.LONG,
            Trend.BEARISH: ProposalDirection.SHORT,
            Trend.SIDEWAYS: ProposalDirection.HOLD,
        }[structure.trend]
        enough = len(candles) >= 3
        if not enough:
            direction = ProposalDirection.HOLD
        stop: float | None = None
        target: float | None = None
        reasons = ["INSUFFICIENT_COMPLETED_CANDLES"]
        confidence = 0.0
        if enough and direction is ProposalDirection.LONG:
            stop = round(float(last[3]), 8)
            target = round(entry + 2 * (entry - stop), 8)
            reasons = ["MARKET_STRUCTURE_BULLISH"]
            confidence = 0.75
        elif enough and direction is ProposalDirection.SHORT:
            stop = round(float(last[2]), 8)
            target = round(entry - 2 * (stop - entry), 8)
            reasons = ["MARKET_STRUCTURE_BEARISH"]
            confidence = 0.75
        elif enough:
            reasons = ["MARKET_STRUCTURE_SIDEWAYS"]
        identity: dict[str, object] = {
            "symbol": symbol.strip(),
            "exchange": exchange.strip(),
            "timeframe": timeframe.strip(),
            "direction": direction.value,
            "entry": entry,
            "stop": stop,
            "target": target,
            "timestamp": timestamp.isoformat(),
            "strategy": self.strategy_id,
            "version": self.strategy_version,
            "reasons": sorted(reasons),
        }
        return TradeProposal(
            proposal_id=TradeProposal.deterministic_id(identity),
            symbol=symbol,
            exchange=exchange,
            timeframe=timeframe,
            direction=direction,
            entry_reference_price=entry,
            stop_loss_candidate=stop,
            take_profit_candidate=target,
            confidence=confidence,
            strategy_id=self.strategy_id,
            strategy_version=self.strategy_version,
            timestamp=timestamp,
            reason_codes=tuple(reasons),
        )


def _timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError("Completed candle timestamp is invalid.")
    try:
        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("Completed candle timestamp is invalid.") from error
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("Completed candle timestamp is invalid.")
    return timestamp


__all__ = ("MarketStructureStrategy",)
