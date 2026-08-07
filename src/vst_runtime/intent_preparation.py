"""Offline composition for one canonical BingX VST Demo execution intent."""

from __future__ import annotations

import hashlib
import hmac
import json
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import (
    ROUND_CEILING,
    ROUND_FLOOR,
    Decimal,
    InvalidOperation,
    localcontext,
)
from pathlib import Path
from typing import Any

from src.data.adapters.models import RecordedMarketDataPayload, RecordedPayloadKind
from src.data.adapters.recorded import RecordedExchangeMarketDataAdapter
from src.data.service import MarketDataService
from src.decision.recorded import DecisionOutcome, DecisionService, RecordedDecision
from src.execution_intent.models import (
    AccountExecutionSnapshot,
    ApprovedRiskSnapshot,
    ExecutionIntent,
    ExecutionPolicy,
    InstrumentConstraints,
    IntentStatus,
    decimal_text,
)
from src.execution_intent.service import ExecutionIntentService
from src.risk.circuit_breaker import CircuitBreaker
from src.risk.drawdown_guard import DrawdownGuard
from src.risk.kill_switch import KillSwitch
from src.risk.portfolio_guard import PortfolioGuard, PortfolioState
from src.risk.position_sizer import PositionSizer
from src.risk.pre_trade_validator import PreTradeValidator
from src.risk.risk_orchestrator import RiskEvaluation, RiskOrchestrator
from src.strategy.market_structure import MarketStructureStrategy
from src.strategy.models import ProposalDirection, TradeProposal
from src.strategy.service import StrategyService
from src.vst_runtime.demo_order import DEFAULT_DEMO_CANARY_POLICY

ClockMs = Callable[[], int]

ARTIFACT_DIRECTORY_NAME = ".operator-artifacts"
MARKET_SCHEMA_VERSION = "bingx-vst-recorded-market-v1"
ACCOUNT_SCHEMA_VERSION = "bingx-vst-account-v1"
CONSTRAINTS_SCHEMA_VERSION = "bingx-vst-constraints-v1"
POLICY_SCHEMA_VERSION = "bingx-vst-execution-policy-v1"

_SENSITIVE_KEY = re.compile(
    r"(?i)(api[_-]?key|api[_-]?secret|authorization|credential|password|"
    r"passphrase|private[_-]?key|secret|signature|token)"
)
_BINGX_SYMBOL = re.compile(r"^[A-Z0-9]+-[A-Z0-9]+$")
_TIMEFRAME = re.compile(r"^[1-9][0-9]*[mhdw]$")
SUPPORTED_DEMO_CANARY_SYMBOLS = frozenset({"BTC-USDT"})


class IntentPreparationError(Exception):
    """Sanitized, stable failure at the manual artifact boundary."""

    def __init__(self, reason_code: str) -> None:
        super().__init__("Intent preparation failed.")
        self.reason_code = reason_code


@dataclass(frozen=True, slots=True)
class IntentPreparationReport:
    """Secret-free result of one local canonical pipeline evaluation."""

    artifact_path: str | None
    intent_digest: str | None
    status: str
    symbol: str | None
    side: str | None
    expires_at: str | None
    proposal_id: str | None
    decision_id: str | None
    risk_evaluation_id: str | None
    reason_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.status, str) or not self.status:
            raise ValueError("status is invalid")
        reasons = tuple(sorted(set(self.reason_codes)))
        if not reasons or any(not item or item != item.strip() for item in reasons):
            raise ValueError("reason_codes are invalid")
        if self.status == IntentStatus.READY.value:
            required = (
                self.artifact_path,
                self.intent_digest,
                self.symbol,
                self.side,
                self.expires_at,
                self.proposal_id,
                self.decision_id,
                self.risk_evaluation_id,
            )
            if any(value is None for value in required):
                raise ValueError("READY preparation report is incomplete")
        object.__setattr__(self, "reason_codes", reasons)

    def to_dict(self) -> dict[str, object]:
        return {
            "artifact_path": self.artifact_path,
            "decision_id": self.decision_id,
            "expires_at": self.expires_at,
            "intent_digest": self.intent_digest,
            "proposal_id": self.proposal_id,
            "reason_codes": list(self.reason_codes),
            "risk_evaluation_id": self.risk_evaluation_id,
            "side": self.side,
            "status": self.status,
            "symbol": self.symbol,
        }

    def to_json(self) -> str:
        return _canonical(self.to_dict())

    @classmethod
    def failure(cls, reason_code: str) -> IntentPreparationReport:
        return cls(
            artifact_path=None,
            intent_digest=None,
            status=IntentStatus.BLOCKED.value,
            symbol=None,
            side=None,
            expires_at=None,
            proposal_id=None,
            decision_id=None,
            risk_evaluation_id=None,
            reason_codes=(reason_code,),
        )


@dataclass(frozen=True, slots=True)
class _MarketInput:
    events: tuple[RecordedMarketDataPayload, ...]
    symbol: str
    exchange: str
    timeframe: str
    digest: str


@dataclass(frozen=True, slots=True)
class _AccountInput:
    execution: AccountExecutionSnapshot
    portfolio: PortfolioState
    observed_at: datetime
    kill_switch_active: bool
    consecutive_losses: int
    digest: str
    current_exposure: Decimal
    used_margin: Decimal


@dataclass(frozen=True, slots=True)
class _PolicyInput:
    execution: ExecutionPolicy
    max_consecutive_losses: int
    circuit_breaker_cooldown_minutes: int
    max_drawdown: float
    max_positions: int
    max_portfolio_risk: float
    max_daily_loss: float
    max_margin_usage: float
    max_position_size: float
    max_leverage: float
    digest: str


@dataclass(frozen=True, slots=True)
class _PreparedInputs:
    market: _MarketInput
    account: _AccountInput
    constraints: InstrumentConstraints
    constraints_observed_at: datetime
    constraints_digest: str
    policy: _PolicyInput


@dataclass(frozen=True, slots=True)
class _CanarySizing:
    quantity: Decimal
    execution_policy: ExecutionPolicy


@dataclass(frozen=True, slots=True)
class _PipelineResult:
    intent: ExecutionIntent
    proposal: TradeProposal
    decision: RecordedDecision
    risk_evaluation_id: str | None


class _ObservedRiskOrchestrator(RiskOrchestrator):
    """Capture the exact evaluation performed by ``DecisionService``."""

    __slots__ = ("evaluation_count", "last_call", "last_evaluation")

    def __init__(
        self,
        kill_switch: KillSwitch,
        circuit_breaker: CircuitBreaker,
        drawdown_guard: DrawdownGuard,
        portfolio_guard: PortfolioGuard,
        pre_trade_validator: PreTradeValidator,
    ) -> None:
        super().__init__(
            kill_switch,
            circuit_breaker,
            drawdown_guard,
            portfolio_guard,
            pre_trade_validator,
        )
        self.evaluation_count = 0
        self.last_call: dict[str, object] | None = None
        self.last_evaluation: RiskEvaluation | None = None

    def evaluate_trade(
        self,
        *,
        portfolio: PortfolioState,
        position_size: float,
        leverage: float,
        entry_price: float,
        stop_loss: float,
    ) -> RiskEvaluation:
        result = super().evaluate_trade(
            portfolio=portfolio,
            position_size=position_size,
            leverage=leverage,
            entry_price=entry_price,
            stop_loss=stop_loss,
        )
        self.evaluation_count += 1
        self.last_call = {
            "entry_price": entry_price,
            "leverage": leverage,
            "position_size": position_size,
            "stop_loss": stop_loss,
        }
        self.last_evaluation = result
        return result


def prepare_demo_canary_intent(
    *,
    market_json: str,
    market_digest: str,
    account_json: str,
    account_digest: str,
    constraints_json: str,
    constraints_digest: str,
    policy_json: str,
    policy_digest: str,
    artifact_directory: Path,
    clock_ms: ClockMs,
) -> IntentPreparationReport:
    """Run frozen local services and persist only a canonical READY intent."""

    failed_reason: str | None = None
    try:
        inputs = _parse_inputs(
            market_json,
            market_digest,
            account_json,
            account_digest,
            constraints_json,
            constraints_digest,
            policy_json,
            policy_digest,
        )
        _validate_freshness(inputs, clock_ms())
        result = _run_pipeline(inputs)
        _validate_freshness(inputs, clock_ms())
        if result.intent.status is not IntentStatus.READY:
            return _report_without_artifact(result)
        if result.intent.source_timestamp != _latest_candle_timestamp(inputs.market):
            raise IntentPreparationError("market_timestamp_mismatch")
        assert result.intent.entry is not None
        if (
            result.intent.entry.price * result.intent.entry.quantity
            > DEFAULT_DEMO_CANARY_POLICY.maximum_notional
        ):
            return _blocked_pipeline_report(result, "canary_notional_exceeded")
        serialized = result.intent.to_json().encode("utf-8")
        digest = hashlib.sha256(serialized).hexdigest()
        relative_path = _write_artifact(
            artifact_directory,
            result.intent.intent_id,
            serialized,
        )
        assert result.intent.source_timestamp is not None
        return IntentPreparationReport(
            artifact_path=relative_path,
            intent_digest=digest,
            status=result.intent.status.value,
            symbol=result.intent.symbol,
            side=result.intent.entry.side.value,
            expires_at=_expiry(result.intent.source_timestamp),
            proposal_id=result.proposal.proposal_id,
            decision_id=result.decision.decision_id,
            risk_evaluation_id=result.risk_evaluation_id,
            reason_codes=tuple(item.value for item in result.intent.reason_codes),
        )
    except IntentPreparationError as error:
        failed_reason = error.reason_code
    except Exception:
        failed_reason = "intent_preparation_failed"
    assert failed_reason is not None
    raise IntentPreparationError(failed_reason) from None


def _parse_inputs(
    market_json: str,
    market_digest: str,
    account_json: str,
    account_digest: str,
    constraints_json: str,
    constraints_digest: str,
    policy_json: str,
    policy_digest: str,
) -> _PreparedInputs:
    market = _parse_market(market_json, market_digest)
    account = _parse_account(account_json, account_digest)
    constraints, observed_at, constraints_digest = _parse_constraints(
        constraints_json, constraints_digest
    )
    policy = _parse_policy(policy_json, policy_digest)
    if market.symbol != constraints.symbol or market.exchange != constraints.exchange:
        raise IntentPreparationError("input_identity_mismatch")
    if account.execution.equity != Decimal(str(account.portfolio.equity)):
        raise IntentPreparationError("account_snapshot_mismatch")
    expected_margin = account.current_exposure / policy.execution.leverage
    if account.used_margin != expected_margin:
        raise IntentPreparationError("account_snapshot_mismatch")
    if (
        account.execution.open_position_quantity != 0
        and account.portfolio.open_positions < 1
    ):
        raise IntentPreparationError("account_snapshot_mismatch")
    return _PreparedInputs(
        market=market,
        account=account,
        constraints=constraints,
        constraints_observed_at=observed_at,
        constraints_digest=constraints_digest,
        policy=policy,
    )


def _parse_market(serialized: str, expected_digest: str) -> _MarketInput:
    values, digest = _load_canonical(
        serialized,
        expected_digest,
        "invalid_market_input",
        "market_input_digest_mismatch",
    )
    _exact_fields(
        values,
        {"events", "exchange", "schema_version", "symbol", "timeframe"},
        "invalid_market_input",
    )
    if values["schema_version"] != MARKET_SCHEMA_VERSION:
        raise IntentPreparationError("unsupported_market_schema")
    symbol = _bingx_symbol(values["symbol"], "invalid_market_input")
    exchange = _text(values["exchange"], "invalid_market_input").casefold()
    timeframe = _timeframe(values["timeframe"], "invalid_market_input")
    if exchange != "bingx":
        raise IntentPreparationError("unsupported_exchange")
    raw_events = values["events"]
    if not isinstance(raw_events, list) or not raw_events:
        raise IntentPreparationError("invalid_market_input")
    events: list[RecordedMarketDataPayload] = []
    previous_sequence: int | None = None
    previous_candle_timestamp: datetime | None = None
    for raw_event in raw_events:
        if not isinstance(raw_event, dict):
            raise IntentPreparationError("invalid_market_input")
        _exact_fields(
            raw_event,
            {"kind", "payload", "sequence"},
            "invalid_market_input",
        )
        sequence = _integer(raw_event["sequence"], "invalid_market_input", zero=True)
        if previous_sequence is not None and sequence <= previous_sequence:
            raise IntentPreparationError("invalid_market_input")
        previous_sequence = sequence
        try:
            kind = RecordedPayloadKind(raw_event["kind"])
            payload = raw_event["payload"]
            if not isinstance(payload, Mapping):
                raise TypeError
            if kind is not RecordedPayloadKind.CANDLES:
                raise TypeError
            if set(payload) != {"candles", "symbol", "timeframe"}:
                raise TypeError
            if (
                payload.get("symbol") != symbol
                or payload.get("timeframe") != timeframe
            ):
                raise TypeError
            candles = payload.get("candles")
            if not isinstance(candles, list) or not candles:
                raise TypeError
            for candle in candles:
                if not isinstance(candle, list) or not candle:
                    raise TypeError
                candle_timestamp = _timestamp(candle[0], "invalid_market_input")
                if (
                    previous_candle_timestamp is not None
                    and candle_timestamp <= previous_candle_timestamp
                ):
                    raise TypeError
                previous_candle_timestamp = candle_timestamp
            event = RecordedMarketDataPayload.from_mapping(
                sequence=sequence,
                kind=kind,
                payload=payload,
            )
        except Exception:
            raise IntentPreparationError("invalid_market_input") from None
        events.append(event)
    return _MarketInput(tuple(events), symbol, exchange, timeframe, digest)


def _parse_account(serialized: str, expected_digest: str) -> _AccountInput:
    values, digest = _load_canonical(
        serialized,
        expected_digest,
        "invalid_account_input",
        "account_input_digest_mismatch",
    )
    _exact_fields(
        values,
        {
            "available_balance",
            "current_exposure",
            "equity",
            "observed_at",
            "open_position_quantity",
            "portfolio",
            "risk_state",
            "schema_version",
        },
        "invalid_account_input",
    )
    if values["schema_version"] != ACCOUNT_SCHEMA_VERSION:
        raise IntentPreparationError("unsupported_account_schema")
    equity = _decimal(values["equity"], "invalid_account_input")
    available = _decimal(
        values["available_balance"], "invalid_account_input", zero=True
    )
    exposure = _decimal(
        values["current_exposure"], "invalid_account_input", zero=True
    )
    open_quantity = _decimal(
        values["open_position_quantity"], "invalid_account_input", zero=True
    )
    if available > equity:
        raise IntentPreparationError("invalid_account_input")
    execution = AccountExecutionSnapshot(
        equity=equity,
        available_balance=available,
        current_exposure=exposure,
        open_position_quantity=open_quantity,
        version=digest,
    )
    raw_portfolio = values["portfolio"]
    if not isinstance(raw_portfolio, dict):
        raise IntentPreparationError("invalid_account_input")
    _exact_fields(
        raw_portfolio,
        {
            "balance",
            "daily_loss",
            "equity",
            "open_positions",
            "total_risk",
            "used_margin",
        },
        "invalid_account_input",
    )
    balance = _decimal(raw_portfolio["balance"], "invalid_account_input")
    portfolio_equity = _decimal(
        raw_portfolio["equity"], "invalid_account_input"
    )
    used_margin = _decimal(
        raw_portfolio["used_margin"], "invalid_account_input", zero=True
    )
    daily_loss = _decimal(
        raw_portfolio["daily_loss"], "invalid_account_input", zero=True
    )
    total_risk = _decimal(
        raw_portfolio["total_risk"], "invalid_account_input", zero=True
    )
    open_positions = _integer(
        raw_portfolio["open_positions"], "invalid_account_input", zero=True
    )
    portfolio = PortfolioState(
        balance=_finite_float(balance, "invalid_account_input"),
        equity=_finite_float(portfolio_equity, "invalid_account_input"),
        used_margin=_finite_float(used_margin, "invalid_account_input"),
        open_positions=open_positions,
        daily_loss=_finite_float(daily_loss, "invalid_account_input"),
        total_risk=_finite_float(total_risk, "invalid_account_input"),
    )
    raw_state = values["risk_state"]
    if not isinstance(raw_state, dict):
        raise IntentPreparationError("invalid_account_input")
    _exact_fields(
        raw_state,
        {"circuit_breaker_consecutive_losses", "kill_switch_active"},
        "invalid_account_input",
    )
    kill_active = raw_state["kill_switch_active"]
    if not isinstance(kill_active, bool):
        raise IntentPreparationError("invalid_account_input")
    losses = _integer(
        raw_state["circuit_breaker_consecutive_losses"],
        "invalid_account_input",
        zero=True,
    )
    return _AccountInput(
        execution=execution,
        portfolio=portfolio,
        observed_at=_timestamp(values["observed_at"], "invalid_account_input"),
        kill_switch_active=kill_active,
        consecutive_losses=losses,
        digest=digest,
        current_exposure=exposure,
        used_margin=used_margin,
    )


def _parse_constraints(
    serialized: str,
    expected_digest: str,
) -> tuple[InstrumentConstraints, datetime, str]:
    values, digest = _load_canonical(
        serialized,
        expected_digest,
        "invalid_constraints_input",
        "constraints_input_digest_mismatch",
    )
    _exact_fields(
        values,
        {
            "exchange",
            "maximum_quantity",
            "minimum_notional",
            "minimum_quantity",
            "observed_at",
            "price_tick",
            "quantity_step",
            "schema_version",
            "symbol",
        },
        "invalid_constraints_input",
    )
    if values["schema_version"] != CONSTRAINTS_SCHEMA_VERSION:
        raise IntentPreparationError("unsupported_constraints_schema")
    exchange = _text(values["exchange"], "invalid_constraints_input").casefold()
    if exchange != "bingx":
        raise IntentPreparationError("unsupported_exchange")
    maximum_raw = values["maximum_quantity"]
    maximum = (
        None
        if maximum_raw is None
        else _decimal(maximum_raw, "invalid_constraints_input")
    )
    constraints = InstrumentConstraints(
        symbol=_bingx_symbol(values["symbol"], "invalid_constraints_input"),
        exchange=exchange,
        price_tick=_decimal(values["price_tick"], "invalid_constraints_input"),
        quantity_step=_decimal(
            values["quantity_step"], "invalid_constraints_input"
        ),
        minimum_quantity=_decimal(
            values["minimum_quantity"], "invalid_constraints_input"
        ),
        minimum_notional=_decimal(
            values["minimum_notional"], "invalid_constraints_input"
        ),
        maximum_quantity=maximum,
        constraints_id=digest,
    )
    observed_at = _timestamp(
        values["observed_at"], "invalid_constraints_input"
    )
    return constraints, observed_at, digest


def _parse_policy(serialized: str, expected_digest: str) -> _PolicyInput:
    values, digest = _load_canonical(
        serialized,
        expected_digest,
        "invalid_policy_input",
        "policy_input_digest_mismatch",
    )
    _exact_fields(
        values,
        {"execution", "risk_limits", "schema_version"},
        "invalid_policy_input",
    )
    if values["schema_version"] != POLICY_SCHEMA_VERSION:
        raise IntentPreparationError("unsupported_policy_schema")
    raw_execution = values["execution"]
    if not isinstance(raw_execution, dict):
        raise IntentPreparationError("invalid_policy_input")
    _exact_fields(
        raw_execution,
        {"leverage", "maximum_exposure_ratio", "risk_percent"},
        "invalid_policy_input",
    )
    execution = ExecutionPolicy(
        risk_percent=_decimal(
            raw_execution["risk_percent"], "invalid_policy_input"
        ),
        leverage=_decimal(raw_execution["leverage"], "invalid_policy_input"),
        maximum_exposure_ratio=_decimal(
            raw_execution["maximum_exposure_ratio"], "invalid_policy_input"
        ),
    )
    raw_limits = values["risk_limits"]
    if not isinstance(raw_limits, dict):
        raise IntentPreparationError("invalid_policy_input")
    _exact_fields(
        raw_limits,
        {
            "circuit_breaker_cooldown_minutes",
            "max_consecutive_losses",
            "max_daily_loss",
            "max_drawdown",
            "max_leverage",
            "max_margin_usage",
            "max_portfolio_risk",
            "max_position_size",
            "max_positions",
        },
        "invalid_policy_input",
    )
    result = _PolicyInput(
        execution=execution,
        max_consecutive_losses=_integer(
            raw_limits["max_consecutive_losses"], "invalid_policy_input"
        ),
        circuit_breaker_cooldown_minutes=_integer(
            raw_limits["circuit_breaker_cooldown_minutes"],
            "invalid_policy_input",
            zero=True,
        ),
        max_drawdown=_finite_float(
            _decimal(raw_limits["max_drawdown"], "invalid_policy_input"),
            "invalid_policy_input",
        ),
        max_positions=_integer(raw_limits["max_positions"], "invalid_policy_input"),
        max_portfolio_risk=_finite_float(
            _decimal(raw_limits["max_portfolio_risk"], "invalid_policy_input"),
            "invalid_policy_input",
        ),
        max_daily_loss=_finite_float(
            _decimal(raw_limits["max_daily_loss"], "invalid_policy_input"),
            "invalid_policy_input",
        ),
        max_margin_usage=_finite_float(
            _decimal(raw_limits["max_margin_usage"], "invalid_policy_input"),
            "invalid_policy_input",
        ),
        max_position_size=_finite_float(
            _decimal(raw_limits["max_position_size"], "invalid_policy_input"),
            "invalid_policy_input",
        ),
        max_leverage=_finite_float(
            _decimal(raw_limits["max_leverage"], "invalid_policy_input"),
            "invalid_policy_input",
        ),
        digest=digest,
    )
    if result.execution.leverage > Decimal(str(result.max_leverage)):
        raise IntentPreparationError("invalid_policy_input")
    if result.execution.leverage != Decimal(
        DEFAULT_DEMO_CANARY_POLICY.maximum_leverage
    ):
        raise IntentPreparationError("canary_leverage_policy_required")
    return result


def _validate_freshness(inputs: _PreparedInputs, now_ms: int) -> None:
    if isinstance(now_ms, bool) or not isinstance(now_ms, int) or now_ms < 1:
        raise IntentPreparationError("invalid_clock")
    policy = DEFAULT_DEMO_CANARY_POLICY
    timestamps = (
        inputs.account.observed_at,
        inputs.constraints_observed_at,
        _latest_candle_timestamp(inputs.market),
    )
    for timestamp in timestamps:
        observed_ms = int(timestamp.timestamp() * 1_000)
        if observed_ms > now_ms + policy.future_tolerance_ms:
            raise IntentPreparationError("input_timestamp_invalid")
        if now_ms > observed_ms + policy.intent_ttl_ms:
            raise IntentPreparationError("stale_input")


def _latest_candle_timestamp(
    market: _MarketInput,
) -> datetime:
    for event in reversed(market.events):
        if event.kind is not RecordedPayloadKind.CANDLES:
            continue
        payload = event.to_mapping()
        if (
            payload.get("symbol") != market.symbol
            or payload.get("timeframe") != market.timeframe
        ):
            continue
        candles = payload.get("candles")
        if not isinstance(candles, list) or not candles:
            raise IntentPreparationError("invalid_market_input")
        last = candles[-1]
        if not isinstance(last, list) or not last:
            raise IntentPreparationError("invalid_market_input")
        return _timestamp(last[0], "invalid_market_input")
    raise IntentPreparationError("canonical_candles_required")


def _run_pipeline(inputs: _PreparedInputs) -> _PipelineResult:
    market = MarketDataService()
    adapter = RecordedExchangeMarketDataAdapter(market, inputs.market.events)
    strategy = StrategyService(MarketStructureStrategy(market))
    started: list[object] = []
    result: _PipelineResult | None = None
    try:
        for core_service in (market, adapter, strategy):
            core_service.initialize()
            started.append(core_service)
            core_service.start()
        adapter.replay()
        proposal = strategy.evaluate(
            symbol=inputs.market.symbol,
            exchange=inputs.market.exchange,
            timeframe=inputs.market.timeframe,
        )
        sizing = _candidate_position_size(proposal, inputs)
        risk = _risk_orchestrator(inputs)
        decision_service = DecisionService(
            risk,
            portfolio=inputs.account.portfolio,
            position_size=float(sizing.quantity),
            leverage=float(sizing.execution_policy.leverage),
        )
        intent_service = ExecutionIntentService()
        for downstream_service in (decision_service, intent_service):
            downstream_service.initialize()
            started.append(downstream_service)
            downstream_service.start()
        decision = decision_service.evaluate(proposal)
        risk_evaluation_id = _risk_evaluation_id(inputs, decision, risk)
        if decision.outcome is DecisionOutcome.APPROVED:
            evaluation = risk.last_evaluation
            if (
                evaluation is None
                or not evaluation.approved
                or risk.evaluation_count != 1
                or risk.last_call is None
                or risk_evaluation_id is None
            ):
                raise IntentPreparationError("risk_approval_unavailable")
            with localcontext() as context:
                context.prec = 50
                approval = ApprovedRiskSnapshot(
                    decision_id=decision.decision_id,
                    maximum_quantity=sizing.quantity,
                    risk_percent=sizing.execution_policy.risk_percent,
                    leverage=sizing.execution_policy.leverage,
                    risk_reference=risk_evaluation_id,
                )
                intent = intent_service.construct(
                    decision,
                    proposal=proposal,
                    account=inputs.account.execution,
                    risk_approval=approval,
                    constraints=inputs.constraints,
                    policy=sizing.execution_policy,
                )
        else:
            intent = intent_service.construct(decision)
        result = _PipelineResult(intent, proposal, decision, risk_evaluation_id)
    finally:
        cleanup_failed = False
        for owned_service in reversed(started):
            try:
                owned_service.stop()  # type: ignore[attr-defined]
            except Exception:
                cleanup_failed = True
        if cleanup_failed:
            raise IntentPreparationError("pipeline_cleanup_failed") from None
    if result is None:
        raise IntentPreparationError("pipeline_failed")
    return result


def _candidate_position_size(
    proposal: TradeProposal,
    inputs: _PreparedInputs,
) -> _CanarySizing:
    if (
        proposal.direction is ProposalDirection.HOLD
        or proposal.stop_loss_candidate is None
    ):
        return _CanarySizing(
            inputs.constraints.minimum_quantity,
            inputs.policy.execution,
        )
    raw_entry = Decimal(str(proposal.entry_reference_price))
    raw_stop = Decimal(str(proposal.stop_loss_candidate))

    if (
        raw_entry <= 0
        or raw_stop <= 0
        or not _has_valid_stop_geometry(
            proposal.direction,
            raw_entry,
            raw_stop,
        )
    ):
        raise IntentPreparationError(
            "canary_stop_distance_unavailable"
        )

    sizing = PositionSizer.calculate_position_size(
        balance=float(inputs.account.execution.equity),
        risk_percent=float(inputs.policy.execution.risk_percent),
        entry_price=float(raw_entry),
        stop_loss=float(raw_stop),
    )
    raw_quantity = Decimal(str(sizing.position_size))

    entry, stop = _normalized_entry_and_stop(
        proposal,
        inputs.constraints,
    )

    if (
        entry <= 0
        or stop <= 0
        or not _has_valid_stop_geometry(
            proposal.direction,
            entry,
            stop,
        )
    ):
        raise IntentPreparationError(
            "canary_stop_distance_unavailable"
        )

    distance = abs(entry - stop)

    normalized_sizing = PositionSizer.calculate_position_size(
        balance=float(inputs.account.execution.equity),
        risk_percent=float(inputs.policy.execution.risk_percent),
        entry_price=float(entry),
        stop_loss=float(stop),
    )
    normalized_raw_quantity = Decimal(str(normalized_sizing.position_size))

    quantity_step = inputs.constraints.quantity_step
    maximum_notional_quantity = _maximum_quantity_for_notional(
        DEFAULT_DEMO_CANARY_POLICY.maximum_notional,
        entry,
        quantity_step,
    )
    caps = (
        maximum_notional_quantity,
        Decimal(str(inputs.policy.max_position_size)),
        normalized_raw_quantity,
        *(
            ()
            if inputs.constraints.maximum_quantity is None
            else (inputs.constraints.maximum_quantity,)
        ),
    )
    capped_quantity = min(raw_quantity, *caps)
    quantity = _ticks(capped_quantity, quantity_step, ROUND_FLOOR)
    if quantity <= 0 or Decimal(str(float(quantity))) != quantity:
        raise IntentPreparationError("canary_size_unavailable")

    if _ticks(normalized_raw_quantity, quantity_step, ROUND_FLOOR) == quantity:
        return _CanarySizing(quantity, inputs.policy.execution)

    # Aim inside the selected exchange step without exceeding the quantity
    # allowed by the canonical risk policy.  The frozen sizer then floors back
    # to the exact quantity already evaluated by DecisionService.
    with localcontext() as context:
        context.prec = 50
        upper_target = min(
            quantity + quantity_step,
            normalized_raw_quantity,
        )
        raw_target = quantity + ((upper_target - quantity) / Decimal(2))
        effective_risk_percent = (
            raw_target
            * distance
            * Decimal(100)
            / inputs.account.execution.equity
        )
        if (
            raw_target <= quantity
            or effective_risk_percent <= 0
            or effective_risk_percent > inputs.policy.execution.risk_percent
        ):
            raise IntentPreparationError("canary_size_unavailable")
        execution_policy = ExecutionPolicy(
            risk_percent=effective_risk_percent,
            leverage=inputs.policy.execution.leverage,
            maximum_exposure_ratio=inputs.policy.execution.maximum_exposure_ratio,
        )
    normalized = PositionSizer.calculate_position_size(
        balance=float(inputs.account.execution.equity),
        risk_percent=float(execution_policy.risk_percent),
        entry_price=float(entry),
        stop_loss=float(stop),
    )
    normalized_quantity = _ticks(
        Decimal(str(normalized.position_size)),
        quantity_step,
        ROUND_FLOOR,
    )
    if normalized_quantity != quantity:
        raise IntentPreparationError("canary_size_unavailable")
    return _CanarySizing(quantity, execution_policy)


def _has_valid_stop_geometry(
    direction: ProposalDirection,
    entry: Decimal,
    stop: Decimal,
) -> bool:
    if direction is ProposalDirection.LONG:
        return stop < entry
    if direction is ProposalDirection.SHORT:
        return stop > entry
    return False


def _normalized_entry_and_stop(
    proposal: TradeProposal,
    constraints: InstrumentConstraints,
) -> tuple[Decimal, Decimal]:
    entry = Decimal(str(proposal.entry_reference_price))
    stop = Decimal(str(proposal.stop_loss_candidate))
    if proposal.direction is ProposalDirection.LONG:
        return (
            _ticks(entry, constraints.price_tick, ROUND_FLOOR),
            _ticks(stop, constraints.price_tick, ROUND_CEILING),
        )
    return (
        _ticks(entry, constraints.price_tick, ROUND_CEILING),
        _ticks(stop, constraints.price_tick, ROUND_FLOOR),
    )


def _ticks(value: Decimal, tick: Decimal, rounding: str) -> Decimal:
    with localcontext() as context:
        context.prec = 50
        return (value / tick).to_integral_value(rounding=rounding) * tick


def _maximum_quantity_for_notional(
    notional: Decimal,
    entry: Decimal,
    quantity_step: Decimal,
) -> Decimal:
    with localcontext() as context:
        context.prec = 50
        return _ticks(notional / entry, quantity_step, ROUND_FLOOR)


def _risk_orchestrator(inputs: _PreparedInputs) -> _ObservedRiskOrchestrator:
    def account_clock() -> datetime:
        return inputs.account.observed_at

    kill_switch = KillSwitch(clock=account_clock)
    if inputs.account.kill_switch_active:
        kill_switch.activate("Canonical account risk state is active.")
    circuit_breaker = CircuitBreaker(
        max_consecutive_losses=inputs.policy.max_consecutive_losses,
        cooldown_minutes=inputs.policy.circuit_breaker_cooldown_minutes,
        clock=account_clock,
    )
    if inputs.account.consecutive_losses > inputs.policy.max_consecutive_losses:
        raise IntentPreparationError("invalid_account_input")
    for _index in range(inputs.account.consecutive_losses):
        circuit_breaker.register_trade(-1.0)
    return _ObservedRiskOrchestrator(
        kill_switch,
        circuit_breaker,
        DrawdownGuard(inputs.policy.max_drawdown),
        PortfolioGuard(
            max_positions=inputs.policy.max_positions,
            max_portfolio_risk=inputs.policy.max_portfolio_risk,
            max_daily_loss=inputs.policy.max_daily_loss,
            max_margin_usage=inputs.policy.max_margin_usage,
        ),
        PreTradeValidator(
            max_position_size=inputs.policy.max_position_size,
            max_leverage=inputs.policy.max_leverage,
        ),
    )


def _risk_evaluation_id(
    inputs: _PreparedInputs,
    decision: RecordedDecision,
    risk: _ObservedRiskOrchestrator,
) -> str | None:
    evaluation = risk.last_evaluation
    call = risk.last_call
    if evaluation is None or call is None:
        return None
    payload = {
        "account_digest": inputs.account.digest,
        "call": call,
        "constraints_digest": inputs.constraints_digest,
        "decision_id": decision.decision_id,
        "market_digest": inputs.market.digest,
        "policy_digest": inputs.policy.digest,
        "result": {
            "approved": evaluation.approved,
            "decision": evaluation.decision.value,
            "drawdown": evaluation.drawdown,
            "reason": evaluation.reason,
        },
    }
    return hashlib.sha256(_canonical(payload).encode()).hexdigest()


def _report_without_artifact(result: _PipelineResult) -> IntentPreparationReport:
    intent = result.intent
    source_timestamp = intent.source_timestamp
    return IntentPreparationReport(
        artifact_path=None,
        intent_digest=None,
        status=intent.status.value,
        symbol=result.proposal.symbol,
        side=None if intent.entry is None else intent.entry.side.value,
        expires_at=None if source_timestamp is None else _expiry(source_timestamp),
        proposal_id=result.proposal.proposal_id,
        decision_id=result.decision.decision_id,
        risk_evaluation_id=result.risk_evaluation_id,
        reason_codes=tuple(item.value for item in intent.reason_codes),
    )


def _blocked_pipeline_report(
    result: _PipelineResult,
    reason_code: str,
) -> IntentPreparationReport:
    return IntentPreparationReport(
        artifact_path=None,
        intent_digest=None,
        status=IntentStatus.BLOCKED.value,
        symbol=result.proposal.symbol,
        side=None if result.intent.entry is None else result.intent.entry.side.value,
        expires_at=(
            None
            if result.intent.source_timestamp is None
            else _expiry(result.intent.source_timestamp)
        ),
        proposal_id=result.proposal.proposal_id,
        decision_id=result.decision.decision_id,
        risk_evaluation_id=result.risk_evaluation_id,
        reason_codes=(reason_code,),
    )


def _write_artifact(directory: Path, intent_id: str, content: bytes) -> str:
    if not isinstance(directory, Path) or directory.name != ARTIFACT_DIRECTORY_NAME:
        raise IntentPreparationError("artifact_directory_invalid")
    if directory.exists() and (not directory.is_dir() or directory.is_symlink()):
        raise IntentPreparationError("artifact_directory_invalid")
    try:
        directory.mkdir(exist_ok=True)
        path = directory / f"{intent_id}.json"
        if path.exists():
            if not path.is_file() or path.is_symlink() or path.read_bytes() != content:
                raise IntentPreparationError("artifact_conflict")
        else:
            with path.open("xb") as stream:
                stream.write(content)
    except IntentPreparationError:
        raise
    except OSError:
        raise IntentPreparationError("artifact_write_failed") from None
    return f"{ARTIFACT_DIRECTORY_NAME}/{intent_id}.json"


def _expiry(source_timestamp: datetime) -> str:
    expires_at = source_timestamp.timestamp() + (
        DEFAULT_DEMO_CANARY_POLICY.intent_ttl_ms / 1_000
    )
    return datetime.fromtimestamp(expires_at, UTC).isoformat().replace("+00:00", "Z")


def _load_canonical(
    serialized: str,
    expected_digest: str,
    reason_code: str,
    digest_reason_code: str,
) -> tuple[dict[str, Any], str]:
    if not isinstance(serialized, str) or not serialized:
        raise IntentPreparationError(reason_code)
    try:
        values = json.loads(serialized)
    except (TypeError, ValueError, json.JSONDecodeError):
        raise IntentPreparationError(reason_code) from None
    if not isinstance(values, dict) or _contains_sensitive_key(values):
        raise IntentPreparationError(reason_code)
    try:
        canonical = _canonical(values)
    except (TypeError, ValueError, OverflowError):
        raise IntentPreparationError(reason_code) from None
    if canonical != serialized:
        raise IntentPreparationError(f"{reason_code}_not_canonical")
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    if (
        not isinstance(expected_digest, str)
        or not hmac.compare_digest(digest, expected_digest.strip().casefold())
    ):
        raise IntentPreparationError(digest_reason_code)
    return values, digest


def _contains_sensitive_key(value: object) -> bool:
    if isinstance(value, dict):
        return any(
            not isinstance(key, str)
            or _SENSITIVE_KEY.search(key) is not None
            or _contains_sensitive_key(item)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return any(_contains_sensitive_key(item) for item in value)
    return False


def _exact_fields(
    values: Mapping[str, object],
    expected: set[str],
    reason_code: str,
) -> None:
    if set(values) != expected:
        raise IntentPreparationError(reason_code)


def _text(value: object, reason_code: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise IntentPreparationError(reason_code)
    return value


def _bingx_symbol(value: object, reason_code: str) -> str:
    symbol = _text(value, reason_code)
    if _BINGX_SYMBOL.fullmatch(symbol) is None:
        raise IntentPreparationError(reason_code)
    if symbol not in SUPPORTED_DEMO_CANARY_SYMBOLS:
        raise IntentPreparationError("unsupported_symbol")
    return symbol


def _timeframe(value: object, reason_code: str) -> str:
    timeframe = _text(value, reason_code)
    if _TIMEFRAME.fullmatch(timeframe) is None:
        raise IntentPreparationError(reason_code)
    return timeframe


def _integer(value: object, reason_code: str, *, zero: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise IntentPreparationError(reason_code)
    if value < 0 or (not zero and value == 0):
        raise IntentPreparationError(reason_code)
    return value


def _decimal(value: object, reason_code: str, *, zero: bool = False) -> Decimal:
    if not isinstance(value, str) or not value:
        raise IntentPreparationError(reason_code)
    try:
        number = Decimal(value)
    except (InvalidOperation, ValueError):
        raise IntentPreparationError(reason_code) from None
    if (
        not number.is_finite()
        or number < 0
        or (not zero and number == 0)
        or decimal_text(number) != value
    ):
        raise IntentPreparationError(reason_code)
    return number.normalize()


def _finite_float(value: Decimal, reason_code: str) -> float:
    number = float(value)
    if number == float("inf") or number == float("-inf"):
        raise IntentPreparationError(reason_code)
    return number


def _timestamp(value: object, reason_code: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise IntentPreparationError(reason_code)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise IntentPreparationError(reason_code) from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise IntentPreparationError(reason_code)
    normalized = parsed.astimezone(UTC)
    if normalized.isoformat().replace("+00:00", "Z") != value:
        raise IntentPreparationError(reason_code)
    return normalized


def _canonical(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )


__all__ = (
    "ACCOUNT_SCHEMA_VERSION",
    "ARTIFACT_DIRECTORY_NAME",
    "CONSTRAINTS_SCHEMA_VERSION",
    "IntentPreparationError",
    "IntentPreparationReport",
    "MARKET_SCHEMA_VERSION",
    "POLICY_SCHEMA_VERSION",
    "SUPPORTED_DEMO_CANARY_SYMBOLS",
    "prepare_demo_canary_intent",
)
