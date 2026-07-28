"""Lifecycle-controlled deterministic execution-intent construction."""

from __future__ import annotations

import hashlib
import json
from threading import RLock

from src.core.lifecycle.service import Service
from src.core.services.models import ServiceDefinition
from src.decision.recorded import DECISION_SERVICE_ID, DecisionOutcome, RecordedDecision
from src.execution_intent.models import (
    AccountExecutionSnapshot,
    ApprovedRiskSnapshot,
    ExecutionIntent,
    ExecutionPolicy,
    InstrumentConstraints,
    IntentOrderType,
    IntentReason,
    IntentSide,
    IntentStatus,
    IntentTimeInForce,
    OrderSpecification,
    decimal_text,
)
from src.execution_intent.sizing import PlanningBlocked, normalize_plan
from src.execution_intent.validation import FrozenExecutionValidationAdapter
from src.strategy.models import ProposalDirection, TradeProposal

EXECUTION_INTENT_SERVICE_ID = "execution-intent"


class ExecutionIntentService(Service):
    def __init__(
        self,
        validator: FrozenExecutionValidationAdapter | None = None,
    ) -> None:
        self._validator = validator or FrozenExecutionValidationAdapter()
        self._running = False
        self._accepted: dict[str, tuple[str, ExecutionIntent]] = {}
        self._lock = RLock()

    def initialize(self) -> None:
        if not callable(getattr(self._validator, "validate", None)):
            raise TypeError("execution validation collaborator is invalid")

    def start(self) -> None:
        with self._lock:
            self._running = True

    def stop(self) -> None:
        with self._lock:
            self._running = False
            self._accepted.clear()

    def definition(self) -> ServiceDefinition:
        return ServiceDefinition(
            EXECUTION_INTENT_SERVICE_ID, self, (DECISION_SERVICE_ID,)
        )

    @property
    def accepted_count(self) -> int:
        with self._lock:
            return len(self._accepted)

    def construct(
        self,
        decision: RecordedDecision,
        *,
        proposal: TradeProposal | None = None,
        account: AccountExecutionSnapshot | None = None,
        risk_approval: ApprovedRiskSnapshot | None = None,
        constraints: InstrumentConstraints | None = None,
        policy: ExecutionPolicy | None = None,
    ) -> ExecutionIntent:
        with self._lock:
            if not self._running:
                raise RuntimeError("Execution intent service is unavailable.")
            if not isinstance(decision, RecordedDecision):
                raise TypeError("decision must be a RecordedDecision")
            if decision.outcome is DecisionOutcome.HOLD:
                return self._simple(
                    decision, IntentStatus.NO_ACTION, IntentReason.DECISION_HOLD
                )
            if decision.outcome is DecisionOutcome.REJECTED:
                return self._simple(
                    decision,
                    IntentStatus.NO_ACTION,
                    IntentReason.DECISION_REJECTED,
                )
            if (
                proposal is None
                or account is None
                or constraints is None
                or policy is None
                or risk_approval is None
                or not isinstance(proposal, TradeProposal)
                or not isinstance(account, AccountExecutionSnapshot)
                or not isinstance(constraints, InstrumentConstraints)
                or not isinstance(policy, ExecutionPolicy)
                or not isinstance(risk_approval, ApprovedRiskSnapshot)
                or proposal.proposal_id != decision.proposal_id
                or risk_approval.decision_id != decision.decision_id
                or risk_approval.risk_percent != policy.risk_percent
                or risk_approval.leverage != policy.leverage
                or proposal.direction is ProposalDirection.HOLD
                or proposal.symbol != constraints.symbol
                or proposal.exchange != constraints.exchange
            ):
                return self._simple(
                    decision, IntentStatus.BLOCKED, IntentReason.INVALID_DECISION
                )
            fingerprint = self._fingerprint(
                decision, proposal, account, risk_approval, constraints, policy
            )
            previous = self._accepted.get(decision.decision_id)
            if previous is not None:
                if previous[0] == fingerprint:
                    return previous[1]
                return self._simple(
                    decision,
                    IntentStatus.BLOCKED,
                    IntentReason.DUPLICATE_CONFLICT,
                    fingerprint=fingerprint,
                )
            try:
                plan = normalize_plan(proposal, account, constraints, policy)
            except PlanningBlocked as error:
                return self._simple(
                    decision,
                    IntentStatus.BLOCKED,
                    error.reason,
                    fingerprint=fingerprint,
                )
            if plan.quantity > risk_approval.maximum_quantity:
                return self._simple(
                    decision,
                    IntentStatus.BLOCKED,
                    IntentReason.QUANTITY_ABOVE_MAXIMUM,
                    fingerprint=fingerprint,
                )
            entry_side = (
                IntentSide.BUY
                if proposal.direction is ProposalDirection.LONG
                else IntentSide.SELL
            )
            protection_side = (
                IntentSide.SELL
                if entry_side is IntentSide.BUY
                else IntentSide.BUY
            )
            entry = OrderSpecification(
                entry_side,
                IntentOrderType.LIMIT,
                plan.entry,
                plan.quantity,
                IntentTimeInForce.GTC,
                False,
            )
            stop = OrderSpecification(
                protection_side,
                IntentOrderType.STOP,
                plan.stop,
                plan.quantity,
                IntentTimeInForce.GTC,
                True,
            )
            target = OrderSpecification(
                protection_side,
                IntentOrderType.TAKE_PROFIT,
                plan.target,
                plan.quantity,
                IntentTimeInForce.GTC,
                True,
            )
            intent = ExecutionIntent(
                intent_id=self._intent_id(
                    fingerprint, IntentStatus.READY, IntentReason.INTENT_READY
                ),
                decision_id=decision.decision_id,
                status=IntentStatus.READY,
                symbol=proposal.symbol,
                exchange=proposal.exchange,
                timeframe=proposal.timeframe,
                entry=entry,
                stop_loss=stop,
                take_profit=target,
                strategy_id=proposal.strategy_id,
                strategy_version=proposal.strategy_version,
                risk_amount=plan.risk_amount,
                constraints_id=constraints.constraints_id,
                source_timestamp=proposal.timestamp,
                reason_codes=(IntentReason.INTENT_READY,),
            )
            try:
                self._validator.validate(intent, account, constraints, policy)
            except Exception:
                return self._simple(
                    decision,
                    IntentStatus.BLOCKED,
                    IntentReason.EXECUTION_CONTRACT_INCOMPATIBLE,
                    fingerprint=fingerprint,
                )
            self._accepted[decision.decision_id] = (fingerprint, intent)
            return intent

    @staticmethod
    def _fingerprint(
        decision: RecordedDecision,
        proposal: TradeProposal,
        account: AccountExecutionSnapshot,
        risk_approval: ApprovedRiskSnapshot,
        constraints: InstrumentConstraints,
        policy: ExecutionPolicy,
    ) -> str:
        values = {
            "account": {
                "available_balance": decimal_text(account.available_balance),
                "current_exposure": decimal_text(account.current_exposure),
                "equity": decimal_text(account.equity),
                "open_position_quantity": decimal_text(
                    account.open_position_quantity
                ),
                "version": account.version,
            },
            "constraints": {
                "constraints_id": constraints.constraints_id,
                "exchange": constraints.exchange,
                "maximum_quantity": (
                    None
                    if constraints.maximum_quantity is None
                    else decimal_text(constraints.maximum_quantity)
                ),
                "minimum_notional": decimal_text(constraints.minimum_notional),
                "minimum_quantity": decimal_text(constraints.minimum_quantity),
                "price_tick": decimal_text(constraints.price_tick),
                "quantity_step": decimal_text(constraints.quantity_step),
                "symbol": constraints.symbol,
            },
            "decision": json.loads(decision.to_json()),
            "risk_approval": {
                "decision_id": risk_approval.decision_id,
                "leverage": decimal_text(risk_approval.leverage),
                "maximum_quantity": decimal_text(
                    risk_approval.maximum_quantity
                ),
                "risk_percent": decimal_text(risk_approval.risk_percent),
                "risk_reference": risk_approval.risk_reference,
            },
            "policy": {
                "leverage": decimal_text(policy.leverage),
                "maximum_exposure_ratio": decimal_text(
                    policy.maximum_exposure_ratio
                ),
                "risk_percent": decimal_text(policy.risk_percent),
            },
            "proposal": json.loads(proposal.to_json()),
        }
        payload = json.dumps(values, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()

    @staticmethod
    def _intent_id(
        fingerprint: str,
        status: IntentStatus,
        reason: IntentReason,
    ) -> str:
        return hashlib.sha256(
            f"{fingerprint}:{status.value}:{reason.value}".encode()
        ).hexdigest()

    def _simple(
        self,
        decision: RecordedDecision,
        status: IntentStatus,
        reason: IntentReason,
        *,
        fingerprint: str | None = None,
    ) -> ExecutionIntent:
        source = fingerprint or hashlib.sha256(
            decision.to_json().encode()
        ).hexdigest()
        return ExecutionIntent(
            intent_id=self._intent_id(source, status, reason),
            decision_id=decision.decision_id,
            status=status,
            symbol=None,
            exchange=None,
            timeframe=None,
            entry=None,
            stop_loss=None,
            take_profit=None,
            strategy_id=None,
            strategy_version=None,
            risk_amount=None,
            constraints_id=None,
            source_timestamp=None,
            reason_codes=(reason,),
        )


__all__ = ("EXECUTION_INTENT_SERVICE_ID", "ExecutionIntentService")
