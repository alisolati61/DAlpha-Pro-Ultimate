"""Validation-only compatibility adapter for frozen Execution contracts."""

from __future__ import annotations

from src.execution.execution_engine import ExecutionEngine, ExecutionRequest
from src.execution_intent.models import (
    AccountExecutionSnapshot,
    ExecutionIntent,
    ExecutionPolicy,
    InstrumentConstraints,
    IntentOrderType,
    IntentStatus,
)
from src.risk.portfolio_guard import PortfolioState


class FrozenExecutionValidationAdapter:
    """Construct and validate an ExecutionRequest without executing it."""

    def validate(
        self,
        intent: ExecutionIntent,
        account: AccountExecutionSnapshot,
        constraints: InstrumentConstraints,
        policy: ExecutionPolicy,
    ) -> None:
        if intent.status is not IntentStatus.READY or intent.entry is None:
            raise ValueError("intent is not execution-ready")
        if intent.stop_loss is None:
            raise ValueError("intent protection is incomplete")
        if intent.entry.order_type is not IntentOrderType.LIMIT:
            raise ValueError("entry order type is incompatible")
        request = ExecutionRequest(
            symbol=constraints.symbol,
            quantity=float(intent.entry.quantity),
            price=float(intent.entry.price),
            leverage=float(policy.leverage),
            stop_loss=float(intent.stop_loss.price),
            portfolio=PortfolioState(
                balance=float(account.equity),
                equity=float(account.equity),
                used_margin=float(
                    account.current_exposure / policy.leverage
                ),
                open_positions=(1 if account.open_position_quantity else 0),
                daily_loss=0.0,
                total_risk=0.0,
            ),
            side=intent.entry.side.value,
            order_type=intent.entry.order_type.value,
        )
        ExecutionEngine._validate_request(request)


__all__ = ("FrozenExecutionValidationAdapter",)
