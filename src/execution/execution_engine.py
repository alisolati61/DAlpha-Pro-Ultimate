"""Validated risk-gated order execution.

The engine preserves the historical boolean contract:

- ``True`` means risk approved, the exchange returned a usable order ID, and
  the order was recorded by ``OrderTracker``.
- ``False`` means risk rejected the request or the exchange returned no usable
  order ID.
- exceptions raised by risk, exchange, clock, or tracker dependencies are not
  hidden.

Requests are normalized without mutating the supplied ``ExecutionRequest``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from math import isfinite
from numbers import Real
from typing import Callable, TypeAlias

from src.domain.order import Order
from src.execution.order_tracker import (
    OrderState,
    OrderStatus,
    OrderTracker,
)
from src.interfaces.exchange_interface import (
    ExchangeInterface,
)
from src.risk.portfolio_guard import PortfolioState
from src.risk.risk_orchestrator import (
    RiskOrchestrator,
)

Clock: TypeAlias = Callable[[], datetime]

_MAX_SYMBOL_LENGTH = 100
_MAX_ORDER_ID_LENGTH = 200
_VALID_SIDES = frozenset({"BUY", "SELL"})
_VALID_ORDER_TYPES = frozenset(
    {
        "MARKET",
        "LIMIT",
    }
)


@dataclass(slots=True)
class ExecutionRequest:
    """Mutable transport request accepted by the execution boundary."""

    symbol: str
    quantity: float
    price: float
    leverage: float
    stop_loss: float
    portfolio: PortfolioState
    side: str = "BUY"
    order_type: str = "LIMIT"


@dataclass(frozen=True, slots=True)
class _NormalizedRequest:
    symbol: str
    quantity: float
    price: float
    leverage: float
    stop_loss: float
    portfolio: PortfolioState
    side: str
    order_type: str


class ExecutionEngine:
    """Validate, risk-check, submit, and track one order."""

    __slots__ = (
        "_clock",
        "exchange",
        "risk",
        "tracker",
    )

    def __init__(
        self,
        risk: RiskOrchestrator,
        exchange: ExchangeInterface,
        tracker: OrderTracker,
        *,
        clock: Clock | None = None,
    ) -> None:
        if not callable(
            getattr(
                risk,
                "validate_trade",
                None,
            )
        ):
            raise TypeError(
                "risk must provide a callable "
                "validate_trade method."
            )

        if not callable(
            getattr(
                exchange,
                "place_order",
                None,
            )
        ):
            raise TypeError(
                "exchange must provide a callable "
                "place_order method."
            )

        if not callable(
            getattr(
                tracker,
                "add",
                None,
            )
        ):
            raise TypeError(
                "tracker must provide a callable "
                "add method."
            )

        if clock is not None and not callable(clock):
            raise TypeError(
                "clock must be callable."
            )

        self.risk = risk
        self.exchange = exchange
        self.tracker = tracker
        self._clock = (
            clock
            if clock is not None
            else _utc_now
        )

    @staticmethod
    def _validate_symbol(
        symbol: object,
    ) -> str:
        if not isinstance(symbol, str):
            raise TypeError(
                "Symbol must be a string."
            )

        normalized = symbol.strip().upper()

        if not normalized:
            raise ValueError(
                "Symbol cannot be empty."
            )

        if len(normalized) > _MAX_SYMBOL_LENGTH:
            raise ValueError(
                "Symbol must not exceed "
                f"{_MAX_SYMBOL_LENGTH} characters."
            )

        return normalized

    @staticmethod
    def _validate_positive_number(
        value: object,
        field_name: str,
        label: str,
    ) -> float:
        if (
            isinstance(value, bool)
            or not isinstance(value, Real)
        ):
            raise TypeError(
                f"{label} must be a number."
            )

        normalized = float(value)

        if not isfinite(normalized):
            raise ValueError(
                f"{label} must be finite."
            )

        if normalized <= 0.0:
            raise ValueError(
                f"{label} must be greater than zero."
            )

        return normalized

    @staticmethod
    def _validate_side(
        side: object,
    ) -> str:
        if not isinstance(side, str):
            raise TypeError(
                "Side must be a string."
            )

        normalized = side.strip().upper()

        if normalized not in _VALID_SIDES:
            raise ValueError(
                "Side must be BUY or SELL."
            )

        return normalized

    @staticmethod
    def _validate_order_type(
        order_type: object,
    ) -> str:
        if not isinstance(order_type, str):
            raise TypeError(
                "Order type must be a string."
            )

        normalized = order_type.strip().upper()

        if normalized not in _VALID_ORDER_TYPES:
            raise ValueError(
                "Order type must be MARKET or LIMIT."
            )

        return normalized

    @classmethod
    def _normalize_request(
        cls,
        request: object,
    ) -> _NormalizedRequest:
        if not isinstance(
            request,
            ExecutionRequest,
        ):
            raise TypeError(
                "request must be an ExecutionRequest."
            )

        symbol = cls._validate_symbol(
            request.symbol
        )
        quantity = cls._validate_positive_number(
            request.quantity,
            "quantity",
            "Quantity",
        )
        price = cls._validate_positive_number(
            request.price,
            "price",
            "Price",
        )
        leverage = cls._validate_positive_number(
            request.leverage,
            "leverage",
            "Leverage",
        )
        stop_loss = cls._validate_positive_number(
            request.stop_loss,
            "stop_loss",
            "Stop loss",
        )

        if not isinstance(
            request.portfolio,
            PortfolioState,
        ):
            raise TypeError(
                "Portfolio must be a PortfolioState."
            )

        side = cls._validate_side(
            request.side
        )
        order_type = cls._validate_order_type(
            request.order_type
        )

        notional = quantity * price

        if not isfinite(notional):
            raise ValueError(
                "Trade notional must be finite."
            )

        risk_distance = (
            abs(price - stop_loss)
            * quantity
        )

        if not isfinite(risk_distance):
            raise ValueError(
                "Trade risk amount must be finite."
            )

        return _NormalizedRequest(
            symbol=symbol,
            quantity=quantity,
            price=price,
            leverage=leverage,
            stop_loss=stop_loss,
            portfolio=request.portfolio,
            side=side,
            order_type=order_type,
        )

    @classmethod
    def _validate_request(
        cls,
        request: ExecutionRequest,
    ) -> None:
        """Preserve the historical private validation helper."""

        cls._normalize_request(request)

    @staticmethod
    def _order_from_normalized(
        request: _NormalizedRequest,
    ) -> Order:
        return Order(
            symbol=request.symbol,
            side=request.side,
            order_type=(
                request.order_type.lower()
            ),
            quantity=request.quantity,
            price=request.price,
        )

    def _build_order(
        self,
        request: ExecutionRequest,
    ) -> Order:
        """Preserve the historical private order builder."""

        normalized = self._normalize_request(
            request
        )
        return self._order_from_normalized(
            normalized
        )

    @staticmethod
    def _normalize_order_id(
        order_id: object,
    ) -> str | None:
        if order_id is None or isinstance(
            order_id,
            bool,
        ):
            return None

        if isinstance(order_id, Real):
            numeric_order_id = float(order_id)

            if (
                not isfinite(numeric_order_id)
                or numeric_order_id <= 0.0
            ):
                return None

        try:
            normalized = str(order_id).strip()
        except Exception:
            return None

        if not normalized:
            return None

        if len(normalized) > _MAX_ORDER_ID_LENGTH:
            return None

        return normalized

    @staticmethod
    def _validate_timestamp(
        timestamp: object,
    ) -> datetime:
        if not isinstance(timestamp, datetime):
            raise TypeError(
                "clock must return a datetime."
            )

        if (
            timestamp.tzinfo is None
            or timestamp.utcoffset() is None
        ):
            raise ValueError(
                "clock must return a "
                "timezone-aware datetime."
            )

        return timestamp.astimezone(UTC)

    def _current_time(self) -> datetime:
        return self._validate_timestamp(
            self._clock()
        )

    def _track_order(
        self,
        *,
        order_id: str,
        order: Order,
        timestamp: datetime | None = None,
    ) -> None:
        normalized_order_id = (
            self._normalize_order_id(
                order_id
            )
        )

        if normalized_order_id is None:
            raise ValueError(
                "order_id must be a non-empty "
                "string representation."
            )

        tracked_at = (
            self._current_time()
            if timestamp is None
            else self._validate_timestamp(
                timestamp
            )
        )

        self.tracker.add(
            OrderState(
                order_id=normalized_order_id,
                symbol=order.symbol,
                quantity=float(
                    order.quantity
                ),
                price=float(
                    order.price or 0.0
                ),
                status=OrderStatus.SENT,
                updated_at=tracked_at,
            )
        )

    def execute(
        self,
        request: ExecutionRequest,
    ) -> bool:
        """Execute one request through validation, risk, exchange, and tracking."""

        normalized = self._normalize_request(
            request
        )

        approved = self.risk.validate_trade(
            portfolio=normalized.portfolio,
            position_size=normalized.quantity,
            leverage=normalized.leverage,
            entry_price=normalized.price,
            stop_loss=normalized.stop_loss,
        )

        if type(approved) is not bool:
            raise TypeError(
                "risk.validate_trade must "
                "return a bool."
            )

        if not approved:
            return False

        # Validate the clock before creating an external order. This prevents a
        # successful exchange submission that cannot be timestamped/tracked.
        tracked_at = self._current_time()

        order = self._order_from_normalized(
            normalized
        )
        exchange_order_id = (
            self.exchange.place_order(order)
        )
        normalized_order_id = (
            self._normalize_order_id(
                exchange_order_id
            )
        )

        if normalized_order_id is None:
            return False

        self._track_order(
            order_id=normalized_order_id,
            order=order,
            timestamp=tracked_at,
        )

        return True


def _utc_now() -> datetime:
    return datetime.now(UTC)


__all__ = (
    "ExecutionEngine",
    "ExecutionRequest",
)