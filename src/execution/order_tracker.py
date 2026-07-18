from __future__ import annotations

import math
from copy import deepcopy
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
    """
    In-memory tracker for the lifecycle of active orders.
    """

    def __init__(self) -> None:
        self._orders: dict[str, OrderState] = {}

    @staticmethod
    def _validate_order_id(
        order_id: str,
    ) -> str:

        if not isinstance(
            order_id,
            str,
        ):

            raise TypeError(
                "order_id must be a string."
            )

        order_id = order_id.strip()

        if not order_id:

            raise ValueError(
                "order_id cannot be empty."
            )

        return order_id

    @staticmethod
    def _validate_symbol(
        symbol: str,
    ) -> str:

        if not isinstance(
            symbol,
            str,
        ):

            raise TypeError(
                "symbol must be a string."
            )

        symbol = symbol.strip()

        if not symbol:

            raise ValueError(
                "symbol cannot be empty."
            )

        return symbol

    @staticmethod
    def _validate_positive_finite(
        value: float,
        name: str,
    ) -> float:

        if not isinstance(
            value,
            (int, float),
        ):

            raise TypeError(
                f"{name} must be a number."
            )

        value = float(value)

        if not math.isfinite(value):

            raise ValueError(
                f"{name} must be finite."
            )

        if value <= 0:

            raise ValueError(
                f"{name} must be greater than zero."
            )

        return value

    @staticmethod
    def _validate_status(
        status: OrderStatus,
    ) -> OrderStatus:

        if not isinstance(
            status,
            OrderStatus,
        ):

            raise TypeError(
                "status must be an OrderStatus."
            )

        return status

    @staticmethod
    def _validate_timestamp(
        timestamp: datetime,
    ) -> datetime:

        if not isinstance(
            timestamp,
            datetime,
        ):

            raise TypeError(
                "updated_at must be a datetime."
            )

        if timestamp.tzinfo is None:

            raise ValueError(
                "updated_at must be timezone-aware."
            )

        return timestamp

    @classmethod
    def _normalize_state(
        cls,
        state: OrderState,
    ) -> OrderState:

        if not isinstance(
            state,
            OrderState,
        ):

            raise TypeError(
                "state must be an OrderState."
            )

        return OrderState(
            order_id=cls._validate_order_id(
                state.order_id
            ),
            symbol=cls._validate_symbol(
                state.symbol
            ),
            quantity=cls._validate_positive_finite(
                state.quantity,
                "quantity",
            ),
            price=cls._validate_positive_finite(
                state.price,
                "price",
            ),
            status=cls._validate_status(
                state.status
            ),
            updated_at=cls._validate_timestamp(
                state.updated_at
            ),
        )

    def add(
        self,
        state: OrderState,
    ) -> None:

        normalized = self._normalize_state(
            state
        )

        if normalized.order_id in self._orders:

            raise ValueError(
                "Order already exists."
            )

        self._orders[
            normalized.order_id
        ] = deepcopy(normalized)

    def update_status(
        self,
        order_id: str,
        status: OrderStatus,
    ) -> None:

        order_id = self._validate_order_id(
            order_id
        )

        status = self._validate_status(
            status
        )

        if order_id not in self._orders:

            raise KeyError(
                f"Unknown order: {order_id}"
            )

        order = self._orders[order_id]

        order.status = status

        order.updated_at = datetime.now(UTC)

    def get(
        self,
        order_id: str,
    ) -> OrderState:

        order_id = self._validate_order_id(
            order_id
        )

        if order_id not in self._orders:

            raise KeyError(
                f"Unknown order: {order_id}"
            )

        return deepcopy(
            self._orders[order_id]
        )

    def exists(
        self,
        order_id: str,
    ) -> bool:

        order_id = self._validate_order_id(
            order_id
        )

        return order_id in self._orders

    def remove(
        self,
        order_id: str,
    ) -> OrderState:

        order_id = self._validate_order_id(
            order_id
        )

        if order_id not in self._orders:

            raise KeyError(
                f"Unknown order: {order_id}"
            )

        return deepcopy(
            self._orders.pop(order_id)
        )

    def count(self) -> int:

        return len(self._orders)