from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum


class OrderStatus(str, Enum):
    CREATED = "CREATED"
    SENT = "SENT"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


@dataclass(slots=True)
class OrderState:
    order_id: str
    symbol: str
    quantity: float
    price: float
    status: OrderStatus
    updated_at: datetime


class OrderTracker:

    def __init__(self) -> None:
        self._orders: dict[str, OrderState] = {}

    def add(self, state: OrderState) -> None:
        self._orders[state.order_id] = state

    def update_status(
        self,
        order_id: str,
        status: OrderStatus,
    ) -> None:

        order = self._orders[order_id]

        order.status = status
        order.updated_at = datetime.now(UTC)

    def get(
        self,
        order_id: str,
    ) -> OrderState:

        return self._orders[order_id]

    def exists(
        self,
        order_id: str,
    ) -> bool:

        return order_id in self._orders