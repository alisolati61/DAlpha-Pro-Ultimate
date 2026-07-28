from __future__ import annotations

import socket

import httpx
import pytest
import websockets

from src.core.kernel.bootstrap import build_runtime
from src.data.adapters.models import RecordedMarketDataPayload, RecordedPayloadKind
from src.data.adapters.recorded import RecordedExchangeMarketDataAdapter
from src.data.service import MarketDataService
from src.decision.recorded import DecisionService
from src.decision.replay import EvaluationPoint, RecordedDecisionCoordinator
from src.execution_intent import (
    AccountExecutionSnapshot,
    ApprovedRiskSnapshot,
    ExecutionIntentService,
    ExecutionPolicy,
    InstrumentConstraints,
    IntentSide,
    IntentStatus,
)
from src.risk.circuit_breaker import CircuitBreaker
from src.risk.drawdown_guard import DrawdownGuard
from src.risk.kill_switch import KillSwitch
from src.risk.portfolio_guard import PortfolioGuard, PortfolioState
from src.risk.pre_trade_validator import PreTradeValidator
from src.risk.risk_orchestrator import RiskOrchestrator
from src.strategy.market_structure import MarketStructureStrategy
from src.strategy.service import StrategyService


def candles(*, bullish: bool) -> list[list[object]]:
    if bullish:
        return [
            ["2026-01-01T00:00:00Z", 99, 101, 98, 100, 1],
            ["2026-01-01T00:01:00Z", 100, 102, 99, 101, 1],
            ["2026-01-01T00:02:00Z", 101, 103, 100, 102, 1],
        ]
    return [
        ["2026-01-01T00:00:00Z", 101, 102, 99, 100, 1],
        ["2026-01-01T00:01:00Z", 100, 101, 98, 99, 1],
        ["2026-01-01T00:02:00Z", 99, 100, 97, 98, 1],
    ]


def composition(*, bullish: bool = True):
    market = MarketDataService()
    adapter = RecordedExchangeMarketDataAdapter(market)
    strategy = StrategyService(MarketStructureStrategy(market))
    risk = RiskOrchestrator(
        KillSwitch(), CircuitBreaker(), DrawdownGuard(), PortfolioGuard(),
        PreTradeValidator(max_position_size=100, max_leverage=10),
    )
    decision = DecisionService(
        risk,
        portfolio=PortfolioState(10000, 10000, 0, 0, 0, 0),
        position_size=1,
        leverage=1,
    )
    intent = ExecutionIntentService()
    coordinator = RecordedDecisionCoordinator(
        adapter, market, strategy, decision
    )
    runtime = build_runtime(
        service_definitions=(
            intent.definition(),
            decision.definition(),
            adapter.definition(),
            strategy.definition(),
            market.definition(),
        )
    )
    payload = RecordedMarketDataPayload.from_mapping(
        sequence=1,
        kind=RecordedPayloadKind.CANDLES,
        payload={
            "symbol": "BTCUSDT",
            "timeframe": "1m",
            "candles": candles(bullish=bullish),
        },
    )
    return runtime, coordinator, strategy, intent, payload


def explicit_inputs(decision_id: str):
    account = AccountExecutionSnapshot(
        "10000", "10000", "0", "0", "account-v1"
    )
    constraints = InstrumentConstraints(
        "BTCUSDT", "recorded", "0.1", "0.01", "0.01", "10", "100",
        "instrument-v1",
    )
    policy = ExecutionPolicy("1", "2", "1")
    risk_approval = ApprovedRiskSnapshot(
        decision_id, "100", "1", "2", "risk-v1"
    )
    return account, constraints, policy, risk_approval


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("bullish", "side"),
    [(True, IntentSide.BUY), (False, IntentSide.SELL)],
)
async def test_recorded_decision_to_ready_intent_is_deterministic(
    bullish: bool,
    side: IntentSide,
) -> None:
    runtime, coordinator, strategy, intent_service, payload = composition(
        bullish=bullish
    )
    await runtime.startup()
    decision = coordinator.replay_and_decide(
        (payload,), (EvaluationPoint(1, "BTCUSDT", "recorded", "1m"),)
    )[0]
    proposal = strategy.evaluate(
        symbol="BTCUSDT", exchange="recorded", timeframe="1m"
    )
    account, constraints, policy, risk_approval = explicit_inputs(
        decision.decision_id
    )
    first = intent_service.construct(
        decision, proposal=proposal, account=account,
        risk_approval=risk_approval, constraints=constraints, policy=policy,
    )
    second = intent_service.construct(
        decision, proposal=proposal, account=account,
        risk_approval=risk_approval, constraints=constraints, policy=policy,
    )
    assert first.status is IntentStatus.READY
    assert first.entry is not None and first.entry.side is side
    assert first is second
    assert first.to_json() == second.to_json()
    assert intent_service.accepted_count == 1
    await runtime.shutdown()
    assert intent_service.accepted_count == 0


@pytest.mark.asyncio
async def test_complete_pipeline_has_zero_external_or_mutation_calls(
    monkeypatch,
) -> None:
    from src.exchange.base import BaseExchange
    from src.exchange.bingx_adapter import BingXAdapter
    from src.exchange.bingx_client import BingXHttpClient
    from src.exchange.ccxt_exchange import CCXTExchange
    from src.execution.execution_engine import ExecutionEngine
    from src.execution.execution_manager import ExecutionManager
    from src.execution.order_manager import OrderManager
    from src.execution.paper_trading import PaperTradingEngine
    from src.execution.portfolio_manager import PortfolioManager
    from src.execution.position_manager import PositionManager

    calls: list[str] = []

    def blocked(name: str):
        def fail(*args, **kwargs):
            calls.append(name)
            raise AssertionError(name)

        return fail

    for owner, name in (
        (ExecutionEngine, "execute"),
        (ExecutionManager, "execute"),
        (ExecutionManager, "execute_many"),
        (OrderManager, "create_order"),
        (PaperTradingEngine, "execute"),
        (PortfolioManager, "add_position"),
        (PortfolioManager, "remove_position"),
        (PositionManager, "open_position"),
        (PositionManager, "close_position"),
        (BaseExchange, "create_order"),
        (BingXAdapter, "create_order"),
        (BingXHttpClient, "place_order"),
        (CCXTExchange, "create_order"),
    ):
        monkeypatch.setattr(owner, name, blocked(f"{owner.__name__}.{name}"))
    monkeypatch.setattr(socket, "socket", blocked("socket"))
    monkeypatch.setattr(httpx, "request", blocked("httpx"))
    monkeypatch.setattr(httpx.Client, "request", blocked("httpx.Client"))
    monkeypatch.setattr(websockets, "connect", blocked("websockets"))
    monkeypatch.setattr("os.getenv", blocked("os.getenv"))

    runtime, coordinator, strategy, intent_service, payload = composition()
    await runtime.startup()
    decision = coordinator.replay_and_decide(
        (payload,), (EvaluationPoint(1, "BTCUSDT", "recorded", "1m"),)
    )[0]
    proposal = strategy.evaluate(
        symbol="BTCUSDT", exchange="recorded", timeframe="1m"
    )
    account, constraints, policy, risk_approval = explicit_inputs(
        decision.decision_id
    )
    result = intent_service.construct(
        decision, proposal=proposal, account=account,
        risk_approval=risk_approval, constraints=constraints, policy=policy,
    )
    await runtime.shutdown()
    assert result.status is IntentStatus.READY
    assert calls == []
