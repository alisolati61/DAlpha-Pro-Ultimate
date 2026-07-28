from __future__ import annotations

import socket

import httpx
import pytest
import websockets

from src.core.kernel.bootstrap import build_runtime
from src.data.adapters.errors import InvalidRecordedPayloadError
from src.data.adapters.models import RecordedMarketDataPayload, RecordedPayloadKind
from src.data.adapters.recorded import RecordedExchangeMarketDataAdapter
from src.data.service import MarketDataService
from src.decision.recorded import DecisionOutcome, DecisionService
from src.decision.replay import (
    EvaluationPoint,
    RecordedDecisionCoordinator,
    RecordedDecisionPipelineError,
)
from src.risk.circuit_breaker import CircuitBreaker
from src.risk.drawdown_guard import DrawdownGuard
from src.risk.kill_switch import KillSwitch
from src.risk.portfolio_guard import PortfolioGuard, PortfolioState
from src.risk.pre_trade_validator import PreTradeValidator
from src.risk.risk_orchestrator import RiskOrchestrator
from src.strategy.market_structure import MarketStructureStrategy
from src.strategy.service import StrategyService


def payload(candles: list[list[object]]) -> RecordedMarketDataPayload:
    return RecordedMarketDataPayload.from_mapping(
        sequence=1,
        kind=RecordedPayloadKind.CANDLES,
        payload={"symbol": "BTCUSDT", "timeframe": "1m", "candles": candles},
    )


def bullish() -> list[list[object]]:
    return [
        ["2026-01-01T00:00:00Z", 99, 101, 98, 100, 1],
        ["2026-01-01T00:01:00Z", 100, 102, 99, 101, 1],
        ["2026-01-01T00:02:00Z", 101, 103, 100, 102, 1],
    ]


def graph(*, size: float = 1):
    market = MarketDataService()
    adapter = RecordedExchangeMarketDataAdapter(market)
    strategy = StrategyService(MarketStructureStrategy(market))
    risk = RiskOrchestrator(
        KillSwitch(), CircuitBreaker(), DrawdownGuard(), PortfolioGuard(),
        PreTradeValidator(max_position_size=10, max_leverage=2),
    )
    decision = DecisionService(
        risk,
        portfolio=PortfolioState(10000, 10000, 0, 0, 0, 0),
        position_size=size,
        leverage=1,
    )
    coordinator = RecordedDecisionCoordinator(
        adapter, market, strategy, decision
    )
    runtime = build_runtime(
        service_definitions=(
            decision.definition(), adapter.definition(),
            strategy.definition(), market.definition(),
        )
    )
    return runtime, coordinator, market


@pytest.mark.asyncio
async def test_recorded_to_approved_decision_and_safe_retry() -> None:
    runtime, coordinator, _ = graph()
    event = payload(bullish())
    point = EvaluationPoint(1, "BTCUSDT", "recorded", "1m")
    await runtime.startup()
    first = coordinator.replay_and_decide((event,), (point,))
    second = coordinator.replay_and_decide((event,), (point,))
    checkpoint = coordinator.checkpoint
    await runtime.shutdown()
    assert len(first) == 1
    assert first[0].outcome is DecisionOutcome.APPROVED
    assert second == ()
    assert checkpoint.replay_sequence == 1
    assert len(checkpoint.decision_ids) == 1


@pytest.mark.asyncio
async def test_risk_rejection_and_hold_paths() -> None:
    runtime, coordinator, _ = graph(size=11)
    await runtime.startup()
    rejected = coordinator.replay_and_decide(
        (payload(bullish()),),
        (EvaluationPoint(1, "BTCUSDT", "recorded", "1m"),),
    )
    await runtime.shutdown()
    assert rejected[0].outcome is DecisionOutcome.REJECTED

    runtime, coordinator, _ = graph()
    await runtime.startup()
    held = coordinator.replay_and_decide(
        (payload(bullish()[:2]),),
        (EvaluationPoint(1, "BTCUSDT", "recorded", "1m"),),
    )
    assert held[0].outcome is DecisionOutcome.HOLD
    await runtime.shutdown()


@pytest.mark.asyncio
async def test_malformed_batch_has_no_canonical_mutation() -> None:
    runtime, coordinator, market = graph()
    await runtime.startup()
    malformed = RecordedMarketDataPayload.from_mapping(
        sequence=1,
        kind=RecordedPayloadKind.CANDLES,
        payload={"symbol": "BTCUSDT", "timeframe": "1m", "candles": []},
    )
    with pytest.raises(InvalidRecordedPayloadError):
        coordinator.replay_and_decide(
            (malformed,),
            (EvaluationPoint(1, "BTCUSDT", "recorded", "1m"),),
        )
    assert market.candle_batch_count == 0
    await runtime.shutdown()


@pytest.mark.asyncio
async def test_failed_evaluation_is_resumed_without_replaying(
    monkeypatch,
) -> None:
    runtime, coordinator, _ = graph()
    event = payload(bullish())
    point = EvaluationPoint(1, "BTCUSDT", "recorded", "1m")
    strategy = coordinator._strategy  # noqa: SLF001
    original = strategy.evaluate
    attempts = 0

    def fail_once(**kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("sensitive internal detail")
        return original(**kwargs)

    monkeypatch.setattr(strategy, "evaluate", fail_once)
    await runtime.startup()
    with pytest.raises(
        RecordedDecisionPipelineError,
        match="Recorded decision evaluation failed",
    ):
        coordinator.replay_and_decide((event,), (point,))
    assert coordinator.checkpoint.replay_sequence == 1
    assert coordinator.checkpoint.pending_evaluation_sequence == 1
    resumed = coordinator.replay_and_decide((event,), (point,))
    assert len(resumed) == 1
    assert coordinator.checkpoint.pending_evaluation_sequence is None
    await runtime.shutdown()


@pytest.mark.asyncio
async def test_pipeline_never_opens_network(monkeypatch) -> None:
    calls = 0

    def blocked(*args, **kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("network call")

    monkeypatch.setattr(socket, "socket", blocked)
    monkeypatch.setattr(httpx, "request", blocked)
    monkeypatch.setattr(httpx.Client, "request", blocked)
    monkeypatch.setattr(websockets, "connect", blocked)
    runtime, coordinator, _ = graph()
    await runtime.startup()
    coordinator.replay_and_decide(
        (payload(bullish()),),
        (EvaluationPoint(1, "BTCUSDT", "recorded", "1m"),),
    )
    await runtime.shutdown()
    assert calls == 0


@pytest.mark.asyncio
async def test_pipeline_never_reaches_order_or_credential_boundaries(
    monkeypatch,
) -> None:
    from src.exchange.base import BaseExchange
    from src.exchange.bingx_adapter import BingXAdapter
    from src.exchange.bingx_client import BingXHttpClient
    from src.exchange.ccxt_exchange import CCXTExchange
    from src.execution.execution_engine import ExecutionEngine
    from src.execution.execution_manager import ExecutionManager
    from src.execution.order_manager import OrderManager

    calls: list[str] = []

    def blocked(name: str):
        def fail(*args, **kwargs):
            calls.append(name)
            raise AssertionError(name)

        return fail

    for owner, name in (
        (ExecutionEngine, "execute"),
        (ExecutionManager, "execute"),
        (OrderManager, "create_order"),
        (BaseExchange, "create_order"),
        (BingXAdapter, "create_order"),
        (BingXHttpClient, "place_order"),
        (CCXTExchange, "create_order"),
    ):
        monkeypatch.setattr(owner, name, blocked(f"{owner.__name__}.{name}"))
    monkeypatch.setattr("os.getenv", blocked("os.getenv"))

    runtime, coordinator, _ = graph()
    await runtime.startup()
    coordinator.replay_and_decide(
        (payload(bullish()),),
        (EvaluationPoint(1, "BTCUSDT", "recorded", "1m"),),
    )
    await runtime.shutdown()
    assert calls == []
