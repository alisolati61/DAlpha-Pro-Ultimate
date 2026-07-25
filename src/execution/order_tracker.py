"""Thread-safe in-memory order lifecycle tracking.

``OrderState`` remains a mutable transport model for compatibility with
exchange adapters. ``OrderTracker`` always stores and returns defensive copies,
so external mutation cannot corrupt tracked state.

The legacy ``update_status`` method preserves unrestricted status updates.
Callers that require lifecycle enforcement should use ``transition_status``.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from math import isfinite
from numbers import Real
from threading import RLock
from typing import Callable, TypeAlias

Clock: TypeAlias = Callable[[], datetime]

_MAX_ORDER_ID_LENGTH = 200
_MAX_SYMBOL_LENGTH = 100


class OrderStatus(str, Enum):
    """Supported execution-order lifecycle states."""

    CREATED = "CREATED"
    SENT = "SENT"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"

    @property
    def terminal(self) -> bool:
        """Return whether no further lifecycle progress is expected."""

        return self in {
            OrderStatus.FILLED,
            OrderStatus.CANCELLED,
            OrderStatus.REJECTED,
        }

    @property
    def active(self) -> bool:
        """Return whether the order is still active."""

        return not self.terminal


_ALLOWED_TRANSITIONS: dict[
    OrderStatus,
    frozenset[OrderStatus],
] = {
    OrderStatus.CREATED: frozenset(
        {
            OrderStatus.SENT,
            OrderStatus.CANCELLED,
            OrderStatus.REJECTED,
        }
    ),
    OrderStatus.SENT: frozenset(
        {
            OrderStatus.PARTIALLY_FILLED,
            OrderStatus.FILLED,
            OrderStatus.CANCELLED,
            OrderStatus.REJECTED,
        }
    ),
    OrderStatus.PARTIALLY_FILLED: frozenset(
        {
            OrderStatus.PARTIALLY_FILLED,
            OrderStatus.FILLED,
            OrderStatus.CANCELLED,
            OrderStatus.REJECTED,
        }
    ),
    OrderStatus.FILLED: frozenset(),
    OrderStatus.CANCELLED: frozenset(),
    OrderStatus.REJECTED: frozenset(),
}


@dataclass(slots=True)
class OrderState:
    """Mutable transport snapshot for one tracked order."""

    order_id: str
    symbol: str
    quantity: float
    price: float
    status: OrderStatus
    updated_at: datetime

    @property
    def terminal(self) -> bool:
        """Return whether the current status is terminal."""

        return (
            isinstance(self.status, OrderStatus)
            and self.status.terminal
        )

    @property
    def active(self) -> bool:
        """Return whether the current status is active."""

        return (
            isinstance(self.status, OrderStatus)
            and self.status.active
        )

    @property
    def notional_value(self) -> float:
        """Return quantity multiplied by price."""

        return float(
            self.quantity
            * self.price
        )


class OrderTracker:
    """Thread-safe in-memory tracker for order lifecycle snapshots."""

    __slots__ = (
        "_clock",
        "_lock",
        "_orders",
    )

    def __init__(
        self,
        *,
        clock: Clock | None = None,
    ) -> None:
        if clock is not None and not callable(clock):
            raise TypeError(
                "clock must be callable."
            )

        self._clock = (
            clock
            if clock is not None
            else _utc_now
        )
        self._lock = RLock()
        self._orders: dict[
            str,
            OrderState,
        ] = {}

    @staticmethod
    def _validate_required_string(
        value: object,
        field_name: str,
        *,
        max_length: int,
    ) -> str:
        if not isinstance(value, str):
            raise TypeError(
                f"{field_name} must be a string."
            )

        normalized = value.strip()

        if not normalized:
            raise ValueError(
                f"{field_name} cannot be empty."
            )

        if len(normalized) > max_length:
            raise ValueError(
                f"{field_name} must not exceed "
                f"{max_length} characters."
            )

        return normalized

    @classmethod
    def _validate_order_id(
        cls,
        order_id: object,
    ) -> str:
        return cls._validate_required_string(
            order_id,
            "order_id",
            max_length=_MAX_ORDER_ID_LENGTH,
        )

    @classmethod
    def _validate_symbol(
        cls,
        symbol: object,
    ) -> str:
        return cls._validate_required_string(
            symbol,
            "symbol",
            max_length=_MAX_SYMBOL_LENGTH,
        )

    @staticmethod
    def _validate_positive_finite(
        value: object,
        name: str,
    ) -> float:
        if (
            isinstance(value, bool)
            or not isinstance(value, Real)
        ):
            raise TypeError(
                f"{name} must be a number."
            )

        normalized = float(value)

        if not isfinite(normalized):
            raise ValueError(
                f"{name} must be finite."
            )

        if normalized <= 0.0:
            raise ValueError(
                f"{name} must be greater than zero."
            )

        return normalized

    @staticmethod
    def _validate_status(
        status: object,
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
        timestamp: object,
    ) -> datetime:
        if not isinstance(
            timestamp,
            datetime,
        ):
            raise TypeError(
                "updated_at must be a datetime."
            )

        if (
            timestamp.tzinfo is None
            or timestamp.utcoffset() is None
        ):
            raise ValueError(
                "updated_at must be timezone-aware."
            )

        return timestamp.astimezone(UTC)

    @classmethod
    def _normalize_state(
        cls,
        state: object,
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

    def _current_time(
        self,
    ) -> datetime:
        return self._validate_timestamp(
            self._clock()
        )

    def add(
        self,
        state: OrderState,
    ) -> None:
        """Add one order after normalization and duplicate checking."""

        normalized = self._normalize_state(
            state
        )

        with self._lock:
            if (
                normalized.order_id
                in self._orders
            ):
                raise ValueError(
                    "Order already exists."
                )

            self._orders[
                normalized.order_id
            ] = deepcopy(normalized)

    def add_many(
        self,
        states: Iterable[OrderState],
    ) -> int:
        """Atomically add multiple order states.

        Every state and every duplicate condition is checked before internal
        state changes. One invalid item therefore leaves the tracker untouched.

        Returns:
            Number of states added.
        """

        if (
            isinstance(
                states,
                (
                    str,
                    bytes,
                    bytearray,
                ),
            )
            or not isinstance(
                states,
                Iterable,
            )
        ):
            raise TypeError(
                "states must be an iterable "
                "of OrderState objects."
            )

        normalized_states = tuple(
            self._normalize_state(state)
            for state in states
        )

        order_ids = tuple(
            state.order_id
            for state in normalized_states
        )

        if len(order_ids) != len(
            set(order_ids)
        ):
            raise ValueError(
                "Duplicate order_id in states."
            )

        with self._lock:
            if any(
                order_id in self._orders
                for order_id in order_ids
            ):
                raise ValueError(
                    "Order already exists."
                )

            for state in normalized_states:
                self._orders[
                    state.order_id
                ] = deepcopy(state)

        return len(normalized_states)

    def update_status(
        self,
        order_id: str,
        status: OrderStatus,
    ) -> None:
        """Update status without transition enforcement.

        This method preserves the historical API. Use ``transition_status``
        when strict lifecycle validation is required.
        """

        normalized_order_id = (
            self._validate_order_id(
                order_id
            )
        )
        normalized_status = (
            self._validate_status(status)
        )

        with self._lock:
            order = self._get_internal(
                normalized_order_id
            )
            timestamp = self._current_time()
            order.status = normalized_status
            order.updated_at = timestamp

    def transition_status(
        self,
        order_id: str,
        status: OrderStatus,
    ) -> None:
        """Update status only when the lifecycle transition is valid."""

        normalized_order_id = (
            self._validate_order_id(
                order_id
            )
        )
        normalized_status = (
            self._validate_status(status)
        )

        with self._lock:
            order = self._get_internal(
                normalized_order_id
            )

            if normalized_status is order.status:
                timestamp = self._current_time()
                order.updated_at = timestamp
                return

            if normalized_status not in (
                _ALLOWED_TRANSITIONS[
                    order.status
                ]
            ):
                raise ValueError(
                    "Invalid order status transition: "
                    f"{order.status.value} -> "
                    f"{normalized_status.value}."
                )

            timestamp = self._current_time()
            order.status = normalized_status
            order.updated_at = timestamp

    @staticmethod
    def can_transition(
        current_status: OrderStatus,
        new_status: OrderStatus,
    ) -> bool:
        """Return whether a strict lifecycle transition is valid."""

        current = OrderTracker._validate_status(
            current_status
        )
        new = OrderTracker._validate_status(
            new_status
        )

        return bool(
            new is current
            or new in _ALLOWED_TRANSITIONS[
                current
            ]
        )

    def get(
        self,
        order_id: str,
    ) -> OrderState:
        """Return a defensive copy of one tracked order."""

        normalized_order_id = (
            self._validate_order_id(
                order_id
            )
        )

        with self._lock:
            return deepcopy(
                self._get_internal(
                    normalized_order_id
                )
            )

    def exists(
        self,
        order_id: str,
    ) -> bool:
        """Return whether an order ID is tracked."""

        normalized_order_id = (
            self._validate_order_id(
                order_id
            )
        )

        with self._lock:
            return (
                normalized_order_id
                in self._orders
            )

    def remove(
        self,
        order_id: str,
    ) -> OrderState:
        """Remove and return a defensive copy of one order."""

        normalized_order_id = (
            self._validate_order_id(
                order_id
            )
        )

        with self._lock:
            if (
                normalized_order_id
                not in self._orders
            ):
                raise KeyError(
                    "Unknown order: "
                    f"{normalized_order_id}"
                )

            return deepcopy(
                self._orders.pop(
                    normalized_order_id
                )
            )

    def all(
        self,
    ) -> list[OrderState]:
        """Return defensive copies in insertion order."""

        with self._lock:
            return deepcopy(
                list(
                    self._orders.values()
                )
            )

    def snapshot(
        self,
    ) -> tuple[OrderState, ...]:
        """Return an independent tuple snapshot in insertion order."""

        return tuple(self.all())

    def by_status(
        self,
        status: OrderStatus,
    ) -> list[OrderState]:
        """Return defensive copies matching one status."""

        normalized_status = (
            self._validate_status(status)
        )

        with self._lock:
            return deepcopy(
                [
                    order
                    for order
                    in self._orders.values()
                    if (
                        order.status
                        is normalized_status
                    )
                ]
            )

    def by_symbol(
        self,
        symbol: str,
    ) -> list[OrderState]:
        """Return defensive copies matching one symbol."""

        normalized_symbol = (
            self._validate_symbol(symbol)
        )

        with self._lock:
            return deepcopy(
                [
                    order
                    for order
                    in self._orders.values()
                    if (
                        order.symbol
                        == normalized_symbol
                    )
                ]
            )

    def active(
        self,
    ) -> list[OrderState]:
        """Return orders whose statuses are not terminal."""

        with self._lock:
            return deepcopy(
                [
                    order
                    for order
                    in self._orders.values()
                    if order.status.active
                ]
            )

    def terminal(
        self,
    ) -> list[OrderState]:
        """Return orders whose statuses are terminal."""

        with self._lock:
            return deepcopy(
                [
                    order
                    for order
                    in self._orders.values()
                    if order.status.terminal
                ]
            )

    def clear(
        self,
    ) -> None:
        """Remove every tracked order."""

        with self._lock:
            self._orders.clear()

    def count(
        self,
    ) -> int:
        """Return the number of tracked orders."""

        return len(self)

    def _get_internal(
        self,
        order_id: str,
    ) -> OrderState:
        try:
            return self._orders[order_id]
        except KeyError as error:
            raise KeyError(
                f"Unknown order: {order_id}"
            ) from error

    def __len__(
        self,
    ) -> int:
        with self._lock:
            return len(self._orders)

    def __bool__(
        self,
    ) -> bool:
        with self._lock:
            return bool(self._orders)

    def __iter__(
        self,
    ) -> Iterator[OrderState]:
        return iter(self.snapshot())


def _utc_now() -> datetime:
    return datetime.now(UTC)


__all__ = (
    "OrderState",
    "OrderStatus",
    "OrderTracker",
)
