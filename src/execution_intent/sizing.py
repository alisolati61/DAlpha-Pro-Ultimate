"""Conservative Decimal normalization around the frozen Risk sizer."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal

from src.execution_intent.models import (
    AccountExecutionSnapshot,
    ExecutionPolicy,
    InstrumentConstraints,
    IntentReason,
    decimal_value,
)
from src.risk.position_sizer import PositionSizer
from src.strategy.models import ProposalDirection, TradeProposal


class PlanningBlocked(Exception):
    def __init__(self, reason: IntentReason) -> None:
        self.reason = reason
        super().__init__(reason.value)


@dataclass(frozen=True, slots=True)
class NormalizedPlan:
    entry: Decimal
    stop: Decimal
    target: Decimal
    quantity: Decimal
    risk_amount: Decimal


def _ticks(value: Decimal, tick: Decimal, rounding: str) -> Decimal:
    return (value / tick).to_integral_value(rounding=rounding) * tick


def normalize_plan(
    proposal: TradeProposal,
    account: AccountExecutionSnapshot,
    constraints: InstrumentConstraints,
    policy: ExecutionPolicy,
) -> NormalizedPlan:
    if proposal.stop_loss_candidate is None or proposal.take_profit_candidate is None:
        raise PlanningBlocked(IntentReason.INVALID_DECISION)
    entry_raw = decimal_value(proposal.entry_reference_price, "entry")
    stop_raw = decimal_value(proposal.stop_loss_candidate, "stop")
    target_raw = decimal_value(proposal.take_profit_candidate, "target")
    if entry_raw == stop_raw:
        raise PlanningBlocked(IntentReason.INVALID_RISK_DISTANCE)
    tick = constraints.price_tick
    if proposal.direction is ProposalDirection.LONG:
        if not stop_raw < entry_raw < target_raw:
            raise PlanningBlocked(IntentReason.INVALID_PRICE_RELATIONSHIP)
        entry = _ticks(entry_raw, tick, ROUND_FLOOR)
        stop = _ticks(stop_raw, tick, ROUND_CEILING)
        target = _ticks(target_raw, tick, ROUND_FLOOR)
        valid = stop < entry < target
    elif proposal.direction is ProposalDirection.SHORT:
        if not target_raw < entry_raw < stop_raw:
            raise PlanningBlocked(IntentReason.INVALID_PRICE_RELATIONSHIP)
        entry = _ticks(entry_raw, tick, ROUND_CEILING)
        stop = _ticks(stop_raw, tick, ROUND_FLOOR)
        target = _ticks(target_raw, tick, ROUND_CEILING)
        valid = target < entry < stop
    else:
        raise PlanningBlocked(IntentReason.INVALID_DECISION)
    if not valid:
        raise PlanningBlocked(IntentReason.NORMALIZATION_INVALIDATED_PROTECTION)
    distance = abs(entry - stop)
    if distance <= 0:
        raise PlanningBlocked(IntentReason.INVALID_RISK_DISTANCE)
    try:
        sized = PositionSizer.calculate_position_size(
            float(account.equity),
            float(policy.risk_percent),
            float(entry),
            float(stop),
        )
    except (TypeError, ValueError, OverflowError) as error:
        raise PlanningBlocked(IntentReason.INVALID_RISK_DISTANCE) from error
    raw_quantity = Decimal(str(sized.position_size))
    quantity = _ticks(raw_quantity, constraints.quantity_step, ROUND_FLOOR)
    if quantity <= 0 or quantity < constraints.minimum_quantity:
        raise PlanningBlocked(IntentReason.QUANTITY_BELOW_MINIMUM)
    if (
        constraints.maximum_quantity is not None
        and quantity > constraints.maximum_quantity
    ):
        raise PlanningBlocked(IntentReason.QUANTITY_ABOVE_MAXIMUM)
    notional = quantity * entry
    if notional < constraints.minimum_notional:
        raise PlanningBlocked(IntentReason.NOTIONAL_BELOW_MINIMUM)
    if notional / policy.leverage > account.available_balance:
        raise PlanningBlocked(IntentReason.INSUFFICIENT_BALANCE)
    maximum_exposure = account.equity * policy.maximum_exposure_ratio
    if account.current_exposure + notional > maximum_exposure:
        raise PlanningBlocked(IntentReason.EXPOSURE_LIMIT)
    approved_risk = Decimal(str(sized.risk_amount))
    if quantity * distance > approved_risk:
        raise PlanningBlocked(IntentReason.EXECUTION_CONTRACT_INCOMPATIBLE)
    return NormalizedPlan(entry, stop, target, quantity, approved_risk)


__all__ = ("NormalizedPlan", "PlanningBlocked", "normalize_plan")
