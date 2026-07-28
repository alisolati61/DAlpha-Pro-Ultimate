from dataclasses import FrozenInstanceError

import pytest

from src.data.data_manager import DataPacket
from src.data.service import MarketDataService
from src.strategy.market_structure import MarketStructureStrategy
from src.strategy.models import ProposalDirection


def service_with(candles: list[list[object]]) -> MarketDataService:
    service = MarketDataService()
    service.initialize()
    service.start()
    service.ingest_candles(DataPacket("BTCUSDT", "1m", candles))
    return service


def test_bullish_proposal_is_immutable_and_byte_deterministic() -> None:
    service = service_with(
        [
            ["2026-01-01T00:00:00Z", 99, 101, 98, 100, 1],
            ["2026-01-01T00:01:00Z", 100, 102, 99, 101, 1],
            ["2026-01-01T00:02:00Z", 101, 103, 100, 102, 1],
        ]
    )
    strategy = MarketStructureStrategy(service)

    first = strategy.evaluate(
        symbol="BTCUSDT", exchange="recorded", timeframe="1m"
    )
    second = strategy.evaluate(
        symbol="BTCUSDT", exchange="recorded", timeframe="1m"
    )

    assert first.direction is ProposalDirection.LONG
    assert first.to_json() == second.to_json()
    assert first.reason_codes == ("MARKET_STRUCTURE_BULLISH",)
    with pytest.raises(FrozenInstanceError):
        first.confidence = 0.0  # type: ignore[misc]


def test_insufficient_candles_returns_hold() -> None:
    service = service_with(
        [
            ["2026-01-01T00:00:00Z", 99, 101, 98, 100, 1],
            ["2026-01-01T00:01:00Z", 100, 102, 99, 101, 1],
        ]
    )
    result = MarketStructureStrategy(service).evaluate(
        symbol="BTCUSDT", exchange="recorded", timeframe="1m"
    )
    assert result.direction is ProposalDirection.HOLD
    assert result.stop_loss_candidate is None


def test_missing_state_is_not_invented() -> None:
    with pytest.raises(ValueError, match="unavailable"):
        MarketStructureStrategy(MarketDataService()).evaluate(
            symbol="BTCUSDT", exchange="recorded", timeframe="1m"
        )
