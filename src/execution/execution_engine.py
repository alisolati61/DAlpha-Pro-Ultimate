from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from src.domain.order import Order
from src.execution.order_tracker import (
    OrderState,
    OrderStatus,
    OrderTracker,
)
from src.interfaces.exchange_interface import ExchangeInterface
from src.risk.portfolio_guard import PortfolioState
from src.risk.risk_orchestrator import RiskOrchestrator


@dataclass(slots=True)
class ExecutionRequest:
    symbol: str
    quantity: float
    price: float
    leverage: float
    stop_loss: float
    portfolio: PortfolioState


class ExecutionEngine:

    def __init__(
        self,
        risk: RiskOrchestrator,
        exchange: ExchangeInterface,
        tracker: OrderTracker,
    ) -> None:

        self.risk = risk
        self.exchange = exchange
        self.tracker = tracker

    def execute(
        self,
        request: ExecutionRequest,
    ) -> bool:

        approved = self.risk.validate_trade(
            portfolio=request.portfolio,
            position_size=request.quantity,
            leverage=request.leverage,
            entry_price=request.price,
            stop_loss=request.stop_loss,
        )

        if not approved:
            return False

        order = Order(
            symbol=request.symbol,
            side="BUY",
            quantity=request.quantity,
            price=request.price,
        )

        exchange_order_id = self.exchange.place_order(order)

        self.tracker.add(
            OrderState(
                order_id=exchange_order_id,
                symbol=request.symbol,
                quantity=request.quantity,
                price=request.price,
                status=OrderStatus.CREATED,
                updated_at=datetime.now(UTC),
            )
        )

        return True