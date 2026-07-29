from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest

from src.core.kernel.bootstrap import build_runtime
from src.data.adapters.models import (
    RecordedMarketDataPayload,
    RecordedPayloadKind,
)
from src.data.adapters.recorded import RecordedExchangeMarketDataAdapter
from src.data.market_data import MarketData
from src.data.service import MarketDataService
from src.decision.recorded import DecisionOutcome, DecisionService
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
from src.paper_runtime import (
    PaperAccountSnapshot,
    PaperExecutionCoordinator,
    PaperExecutionPolicy,
    PaperMarketEvent,
    PaperReason,
    PaperReconciler,
    ReconciliationStatus,
)
from src.risk.circuit_breaker import CircuitBreaker
from src.risk.drawdown_guard import DrawdownGuard
from src.risk.kill_switch import KillSwitch
from src.risk.portfolio_guard import PortfolioGuard, PortfolioState
from src.risk.pre_trade_validator import PreTradeValidator
from src.risk.risk_orchestrator import RiskOrchestrator
from src.strategy.market_structure import MarketStructureStrategy
from src.strategy.service import StrategyService


def _candles(direction: str) -> list[list[object]]:
    if direction == "long":
        closes = (100, 101, 102)
    elif direction == "short":
        closes = (100, 99, 98)
    else:
        closes = (100, 100, 100)
    return [
        [
            f"2026-01-01T00:0{index}:00Z",
            close,
            close + 1,
            close - 1,
            close,
            100,
        ]
        for index, close in enumerate(closes)
    ]


def _starting_account() -> PaperAccountSnapshot:
    return PaperAccountSnapshot(
        "10000", "10000", "10000", "0", "0", "0", "0", "0", 0
    )


def _composition(
    direction: str,
    *,
    risk_position_limit: float = 100,
    fill_cap: str = "1000",
):
    market = MarketDataService()
    adapter = RecordedExchangeMarketDataAdapter(market)
    strategy = StrategyService(MarketStructureStrategy(market))
    risk = RiskOrchestrator(
        KillSwitch(),
        CircuitBreaker(),
        DrawdownGuard(),
        PortfolioGuard(),
        PreTradeValidator(
            max_position_size=risk_position_limit,
            max_leverage=10,
        ),
    )
    decision = DecisionService(
        risk,
        portfolio=PortfolioState(10000, 10000, 0, 0, 0, 0),
        position_size=1,
        leverage=1,
    )
    intent_service = ExecutionIntentService()
    paper = PaperExecutionCoordinator(
        PaperExecutionPolicy(
            "paper-integration-v1",
            "10",
            "5",
            fill_cap,
            "0.01",
            "2",
            "instrument-v1",
        ),
        _starting_account(),
    )
    replay = RecordedDecisionCoordinator(
        adapter, market, strategy, decision
    )
    runtime = build_runtime(
        service_definitions=(
            paper.definition(),
            intent_service.definition(),
            decision.definition(),
            adapter.definition(),
            strategy.definition(),
            market.definition(),
        )
    )
    source = RecordedMarketDataPayload.from_mapping(
        sequence=1,
        kind=RecordedPayloadKind.CANDLES,
        payload={
            "symbol": "BTCUSDT",
            "timeframe": "1m",
            "candles": _candles(direction),
        },
    )
    return (
        runtime,
        replay,
        adapter,
        market,
        strategy,
        intent_service,
        paper,
        source,
    )


def _planning_inputs(decision_id: str):
    return (
        AccountExecutionSnapshot(
            "10000", "10000", "0", "0", "account-v1"
        ),
        InstrumentConstraints(
            "BTCUSDT",
            "recorded",
            "0.1",
            "0.01",
            "0.01",
            "10",
            "100",
            "instrument-v1",
        ),
        ExecutionPolicy("0.5", "2", "1"),
        ApprovedRiskSnapshot(
            decision_id, "100", "0.5", "2", "risk-v1"
        ),
    )


def _snapshot_payload(
    sequence: int,
    *,
    price: Decimal,
    timestamp,
    quantity: Decimal,
) -> RecordedMarketDataPayload:
    return RecordedMarketDataPayload.from_mapping(
        sequence=sequence,
        kind=RecordedPayloadKind.SNAPSHOT,
        payload={
            "ask": float(price + Decimal("0.1")),
            "bid": float(price - Decimal("0.1")),
            "exchange": "recorded",
            "price": float(price),
            "symbol": "BTCUSDT",
            "timeframe": "1m",
            "timestamp": timestamp.isoformat().replace("+00:00", "Z"),
            "volume": float(quantity),
        },
    )


def _paper_event(
    sequence: int,
    snapshot: MarketData,
    source: RecordedMarketDataPayload,
) -> PaperMarketEvent:
    return PaperMarketEvent(
        sequence,
        snapshot.symbol,
        snapshot.timestamp,
        Decimal(str(snapshot.price)),
        Decimal(str(min(snapshot.bid, snapshot.price))),
        Decimal(str(max(snapshot.ask, snapshot.price))),
        Decimal(str(snapshot.volume)),
        snapshot.exchange,
        snapshot.timeframe,
        source.digest,
    )


def _construct_intent(
    replay: RecordedDecisionCoordinator,
    strategy: StrategyService,
    intent_service: ExecutionIntentService,
    source: RecordedMarketDataPayload,
):
    decision = replay.replay_and_decide(
        (source,),
        (EvaluationPoint(1, "BTCUSDT", "recorded", "1m"),),
    )[0]
    proposal = strategy.evaluate(
        symbol="BTCUSDT", exchange="recorded", timeframe="1m"
    )
    account, constraints, policy, approval = _planning_inputs(
        decision.decision_id
    )
    intent = intent_service.construct(
        decision,
        proposal=proposal,
        account=account,
        risk_approval=approval,
        constraints=constraints,
        policy=policy,
    )
    return decision, proposal, intent


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("direction", "side"),
    (("long", IntentSide.BUY), ("short", IntentSide.SELL)),
)
async def test_recorded_ready_intent_executes_and_reconciles(
    direction: str,
    side: IntentSide,
) -> None:
    (
        runtime,
        replay,
        adapter,
        market,
        strategy,
        intent_service,
        paper,
        source,
    ) = _composition(direction)
    await runtime.startup()
    decision, proposal, intent = _construct_intent(
        replay, strategy, intent_service, source
    )
    assert decision.outcome is DecisionOutcome.APPROVED
    assert intent.status is IntentStatus.READY
    assert intent.entry is not None and intent.entry.side is side
    submission = paper.submit_intent(intent, source_sequence=1)
    assert submission.accepted and submission.order is not None

    entry_source = _snapshot_payload(
        2,
        price=intent.entry.price,
        timestamp=proposal.timestamp + timedelta(minutes=1),
        quantity=intent.entry.quantity,
    )
    adapter.replay((entry_source,))
    entry_snapshot = market.latest_snapshot(
        "BTCUSDT", "recorded", "1m"
    )
    assert entry_snapshot is not None
    paper.advance_market(_paper_event(2, entry_snapshot, entry_source))
    expected_position_side = "LONG" if side is IntentSide.BUY else "SHORT"
    assert paper.position("BTCUSDT").side == expected_position_side

    assert intent.take_profit is not None
    exit_source = _snapshot_payload(
        3,
        price=intent.take_profit.price,
        timestamp=proposal.timestamp + timedelta(minutes=2),
        quantity=intent.entry.quantity,
    )
    adapter.replay((exit_source,))
    exit_snapshot = market.latest_snapshot(
        "BTCUSDT", "recorded", "1m"
    )
    assert exit_snapshot is not None
    paper.advance_market(_paper_event(3, exit_snapshot, exit_source))
    report = paper.report(submission.order.order_id)
    result = PaperReconciler().reconcile(report)

    assert paper.position("BTCUSDT").side == "FLAT"
    assert paper.account.realized_pnl > 0
    assert result.status is ReconciliationStatus.MATCHED
    assert report.report_id == report.report_id
    checkpoint = paper.export_checkpoint()
    assert checkpoint.digest
    await runtime.shutdown()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("direction", "risk_position_limit", "expected_status"),
    (
        ("hold", 100, IntentStatus.NO_ACTION),
        ("long", 0.5, IntentStatus.NO_ACTION),
    ),
)
async def test_hold_and_risk_rejection_never_mutate_paper_account(
    direction: str,
    risk_position_limit: float,
    expected_status: IntentStatus,
) -> None:
    (
        runtime,
        replay,
        _,
        _,
        strategy,
        intent_service,
        paper,
        source,
    ) = _composition(direction, risk_position_limit=risk_position_limit)
    await runtime.startup()
    _, _, intent = _construct_intent(
        replay, strategy, intent_service, source
    )
    before = paper.export_checkpoint()
    result = paper.submit_intent(intent, source_sequence=1)

    assert intent.status is expected_status
    assert not result.accepted
    assert result.reason is PaperReason.INTENT_NOT_READY
    assert paper.account == _starting_account()
    assert paper.fills == ()
    assert paper.export_checkpoint() == before
    await runtime.shutdown()
