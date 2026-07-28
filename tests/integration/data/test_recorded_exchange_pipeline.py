"""Explicit runtime composition for recorded exchange payload replay."""

from __future__ import annotations

import pytest

from src.core.kernel.bootstrap import build_runtime
from src.core.services.errors import MissingServiceDependencyError
from src.core.services.models import ServiceState
from src.data.adapters.models import (
    RecordedMarketDataPayload,
    RecordedPayloadKind,
)
from src.data.adapters.recorded import (
    RECORDED_MARKET_DATA_ADAPTER_ID,
    RecordedExchangeMarketDataAdapter,
)
from src.data.service import MARKET_DATA_SERVICE_ID, MarketDataService


def payload() -> RecordedMarketDataPayload:
    return RecordedMarketDataPayload.from_mapping(
        sequence=1,
        kind=RecordedPayloadKind.SNAPSHOT,
        payload={
            "symbol": "BTCUSDT",
            "exchange": "recorded",
            "timeframe": "1m",
            "price": 100,
            "bid": 99,
            "ask": 101,
            "volume": 1,
            "timestamp": "2026-01-01T00:00:00Z",
        },
    )


@pytest.mark.asyncio
async def test_runtime_starts_target_before_adapter_and_replays() -> None:
    service = MarketDataService()
    adapter = RecordedExchangeMarketDataAdapter(service, (payload(),))
    runtime = build_runtime(
        service_definitions=(
            adapter.definition(),
            service.definition(),
        )
    )

    await runtime.startup()
    result = adapter.replay()

    assert result.applied == 1
    assert runtime.lifecycle_manager.state_of(
        MARKET_DATA_SERVICE_ID
    ) is ServiceState.RUNNING
    assert runtime.lifecycle_manager.state_of(
        RECORDED_MARKET_DATA_ADAPTER_ID
    ) is ServiceState.RUNNING
    assert service.snapshot_count == 1

    await runtime.shutdown()

    assert runtime.lifecycle_manager.state_of(
        RECORDED_MARKET_DATA_ADAPTER_ID
    ) is ServiceState.STOPPED
    assert runtime.lifecycle_manager.state_of(
        MARKET_DATA_SERVICE_ID
    ) is ServiceState.STOPPED
    assert service.snapshot_count == 0


@pytest.mark.asyncio
async def test_adapter_is_never_auto_wired() -> None:
    runtime = build_runtime()

    assert runtime.service_definitions == ()
    assert not hasattr(runtime, "recorded_market_data_adapter")

    await runtime.startup()
    await runtime.shutdown()


@pytest.mark.asyncio
async def test_missing_explicit_market_data_dependency_blocks_lifecycle() -> None:
    service = MarketDataService()

    class TrackingAdapter(RecordedExchangeMarketDataAdapter):
        initialize_calls = 0

        def initialize(self) -> None:
            self.initialize_calls += 1
            super().initialize()

    adapter = TrackingAdapter(service)
    runtime = build_runtime(
        service_definitions=(adapter.definition(),)
    )

    with pytest.raises(MissingServiceDependencyError):
        await runtime.startup()

    assert adapter.initialize_calls == 0
    assert service.snapshot_count == 0
