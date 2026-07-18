from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

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

    side: str = "BUY"

    order_type: str = "LIMIT"


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

    @staticmethod
    def _validate_request(
        request: ExecutionRequest,
    ) -> None:

        if not isinstance(
            request.symbol,
            str,
        ):

            raise TypeError(
                "Symbol must be a string."
            )

        if not request.symbol.strip():

            raise ValueError(
                "Symbol cannot be empty."
            )

        if request.quantity <= 0:

            raise ValueError(
                "Quantity must be greater than zero."
            )

        if request.price <= 0:

            raise ValueError(
                "Price must be greater than zero."
            )

        if request.leverage <= 0:

            raise ValueError(
                "Leverage must be greater than zero."
            )

        if request.stop_loss <= 0:

            raise ValueError(
                "Stop loss must be greater than zero."
            )

        side = request.side.upper()

        if side not in {
            "BUY",
            "SELL",
        }:

            raise ValueError(
                "Side must be BUY or SELL."
            )

        order_type = request.order_type.upper()

        if order_type not in {
            "MARKET",
            "LIMIT",
        }:

            raise ValueError(
                "Order type must be MARKET or LIMIT."
            )

    def _build_order(
        self,
        request: ExecutionRequest,
    ) -> Order:

        return Order(
            symbol=request.symbol.strip().upper(),
            side=request.side.upper(),
            order_type=request.order_type.lower(),
            quantity=float(
                request.quantity
            ),
            price=float(
                request.price
            ),
        )

    def _track_order(
        self,
        *,
        order_id: str,
        order: Order,
    ) -> None:

        self.tracker.add(
            OrderState(
                order_id=order_id,
                symbol=order.symbol,
                quantity=float(
                    order.quantity
                ),
                price=float(
                    order.price or 0.0
                ),
                status=OrderStatus.SENT,
                updated_at=datetime.now(UTC),
            )
        )

    def execute(
        self,
        request: ExecutionRequest,
    ) -> bool:

        self._validate_request(
            request
        )

        approved = self.risk.validate_trade(
            portfolio=request.portfolio,
            position_size=request.quantity,
            leverage=request.leverage,
            entry_price=request.price,
            stop_loss=request.stop_loss,
        )

        if not approved:

            return False

        order = self._build_order(
            request
        )

        exchange_order_id = (
            self.exchange.place_order(
                order
            )
        )

        if not exchange_order_id:

            return False

        self._track_order(
            order_id=str(
                exchange_order_id
            ),
            order=order,
        )

        return True