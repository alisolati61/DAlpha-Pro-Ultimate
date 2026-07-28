"""Deterministic proposal decision and frozen-risk integration."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum

from src.core.lifecycle.service import Service
from src.core.services.models import ServiceDefinition
from src.risk.portfolio_guard import PortfolioState
from src.risk.risk_orchestrator import RiskOrchestrator
from src.strategy.models import ProposalDirection, TradeProposal
from src.strategy.service import STRATEGY_SERVICE_ID

DECISION_SERVICE_ID = "decision"


class DecisionOutcome(str, Enum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    HOLD = "HOLD"


@dataclass(frozen=True, slots=True)
class RecordedDecision:
    decision_id: str
    proposal_id: str
    outcome: DecisionOutcome
    reason_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.decision_id or not self.proposal_id:
            raise ValueError("decision identifiers must not be empty")
        if not isinstance(self.outcome, DecisionOutcome):
            raise TypeError("outcome must be a DecisionOutcome")
        reasons = tuple(sorted(set(self.reason_codes)))
        if not reasons:
            raise ValueError("reason_codes must not be empty")
        object.__setattr__(self, "reason_codes", reasons)

    def to_json(self) -> str:
        return json.dumps(
            {
                "decision_id": self.decision_id,
                "outcome": self.outcome.value,
                "proposal_id": self.proposal_id,
                "reason_codes": list(self.reason_codes),
            },
            sort_keys=True,
            separators=(",", ":"),
        )


class DecisionService(Service):
    def __init__(
        self,
        risk: RiskOrchestrator,
        *,
        portfolio: PortfolioState,
        position_size: float,
        leverage: float,
    ) -> None:
        if not isinstance(risk, RiskOrchestrator):
            raise TypeError("risk must be a RiskOrchestrator")
        if not isinstance(portfolio, PortfolioState):
            raise TypeError("portfolio must be a PortfolioState")
        self._risk = risk
        self._portfolio = portfolio
        self._position_size = position_size
        self._leverage = leverage
        self._running = False

    def initialize(self) -> None:
        pass

    def start(self) -> None:
        self._running = True

    def stop(self) -> None:
        self._running = False

    def definition(self) -> ServiceDefinition:
        return ServiceDefinition(
            DECISION_SERVICE_ID, self, (STRATEGY_SERVICE_ID,)
        )

    def evaluate(self, proposal: TradeProposal) -> RecordedDecision:
        if not self._running:
            raise RuntimeError("Decision service is unavailable.")
        if not isinstance(proposal, TradeProposal):
            raise TypeError("proposal is invalid")
        if proposal.direction is ProposalDirection.HOLD:
            return _decision(
                proposal, DecisionOutcome.HOLD, proposal.reason_codes
            )
        entry = proposal.entry_reference_price
        stop = proposal.stop_loss_candidate
        target = proposal.take_profit_candidate
        invalid = (
            stop is None
            or target is None
            or (
                proposal.direction is ProposalDirection.LONG
                and not (stop < entry < target)
            )
            or (
                proposal.direction is ProposalDirection.SHORT
                and not (target < entry < stop)
            )
        )
        if invalid:
            return _decision(
                proposal,
                DecisionOutcome.REJECTED,
                (*proposal.reason_codes, "INVALID_PRICE_RELATIONSHIP"),
            )
        assert stop is not None
        try:
            result = self._risk.evaluate_trade(
                portfolio=self._portfolio,
                position_size=self._position_size,
                leverage=self._leverage,
                entry_price=entry,
                stop_loss=stop,
            )
        except Exception:
            return _decision(
                proposal,
                DecisionOutcome.REJECTED,
                (*proposal.reason_codes, "RISK_EVALUATION_FAILED"),
            )
        if not result.approved:
            return _decision(
                proposal,
                DecisionOutcome.REJECTED,
                (*proposal.reason_codes, f"RISK_{result.decision.value}"),
            )
        return _decision(
            proposal,
            DecisionOutcome.APPROVED,
            (*proposal.reason_codes, "RISK_APPROVED"),
        )


def _decision(
    proposal: TradeProposal,
    outcome: DecisionOutcome,
    reasons: tuple[str, ...],
) -> RecordedDecision:
    normalized = tuple(sorted(set(reasons)))
    source = json.dumps(
        {
            "proposal_id": proposal.proposal_id,
            "outcome": outcome.value,
            "reasons": normalized,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return RecordedDecision(
        decision_id=hashlib.sha256(source.encode("utf-8")).hexdigest(),
        proposal_id=proposal.proposal_id,
        outcome=outcome,
        reason_codes=normalized,
    )


__all__ = (
    "DECISION_SERVICE_ID",
    "DecisionOutcome",
    "DecisionService",
    "RecordedDecision",
)
