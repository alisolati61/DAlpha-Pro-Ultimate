"""Immutable execution reports and validated report factories.

``ExecutionReport`` is intentionally a passive transport model. Direct
construction remains permissive because exchange adapters may need to carry a
raw report to a downstream validation boundary.

``ExecutionReportFactory`` is the safe construction path for reports created
inside the execution subsystem. It normalizes strings, validates numeric
fields, and always produces timezone-aware UTC timestamps.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from math import isfinite
from numbers import Real

_MAX_ORDER_ID_LENGTH = 200
_MAX_SYMBOL_LENGTH = 100
_MAX_MESSAGE_LENGTH = 500


@dataclass(frozen=True, slots=True)
class ExecutionReport:
    """Immutable execution outcome.

    Direct construction does not validate field combinations. This preserves
    compatibility with exchange adapters and downstream validators that may
    need to inspect malformed external reports safely.
    """

    order_id: str
    symbol: str
    success: bool
    quantity: float
    executed_price: float
    message: str
    timestamp: datetime

    @property
    def failed(self) -> bool:
        """Return whether the execution was unsuccessful."""

        return not self.success

    @property
    def notional_value(self) -> float:
        """Return executed quantity multiplied by execution price."""

        return float(
            self.quantity
            * self.executed_price
        )


class ExecutionReportFactory:
    """Create normalized and validated immutable execution reports."""

    @staticmethod
    def _normalize_required_string(
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

    @staticmethod
    def _normalize_positive_number(
        value: object,
        field_name: str,
    ) -> float:
        if (
            isinstance(value, bool)
            or not isinstance(value, Real)
        ):
            raise TypeError(
                f"{field_name} must be a real number."
            )

        normalized = float(value)

        if not isfinite(normalized):
            raise ValueError(
                f"{field_name} must be finite."
            )

        if normalized <= 0.0:
            raise ValueError(
                f"{field_name} must be greater than zero."
            )

        return normalized

    @staticmethod
    def _normalize_timestamp(
        timestamp: object | None,
    ) -> datetime:
        if timestamp is None:
            return datetime.now(UTC)

        if not isinstance(timestamp, datetime):
            raise TypeError(
                "timestamp must be a datetime."
            )

        if timestamp.tzinfo is None:
            raise ValueError(
                "timestamp must be timezone-aware."
            )

        return timestamp.astimezone(UTC)

    @classmethod
    def success(
        cls,
        order_id: str,
        symbol: str,
        quantity: Real,
        price: Real,
        *,
        timestamp: datetime | None = None,
    ) -> ExecutionReport:
        """Create a validated successful execution report."""

        normalized_order_id = (
            cls._normalize_required_string(
                order_id,
                "order_id",
                max_length=_MAX_ORDER_ID_LENGTH,
            )
        )
        normalized_symbol = (
            cls._normalize_required_string(
                symbol,
                "symbol",
                max_length=_MAX_SYMBOL_LENGTH,
            )
        )
        normalized_quantity = (
            cls._normalize_positive_number(
                quantity,
                "quantity",
            )
        )
        normalized_price = (
            cls._normalize_positive_number(
                price,
                "price",
            )
        )
        normalized_timestamp = (
            cls._normalize_timestamp(
                timestamp
            )
        )

        return ExecutionReport(
            order_id=normalized_order_id,
            symbol=normalized_symbol,
            success=True,
            quantity=normalized_quantity,
            executed_price=normalized_price,
            message="Order executed.",
            timestamp=normalized_timestamp,
        )

    @classmethod
    def failed(
        cls,
        symbol: str,
        message: str,
        *,
        timestamp: datetime | None = None,
    ) -> ExecutionReport:
        """Create a validated failed execution report."""

        normalized_symbol = (
            cls._normalize_required_string(
                symbol,
                "symbol",
                max_length=_MAX_SYMBOL_LENGTH,
            )
        )
        normalized_message = (
            cls._normalize_required_string(
                message,
                "message",
                max_length=_MAX_MESSAGE_LENGTH,
            )
        )
        normalized_timestamp = (
            cls._normalize_timestamp(
                timestamp
            )
        )

        return ExecutionReport(
            order_id="",
            symbol=normalized_symbol,
            success=False,
            quantity=0.0,
            executed_price=0.0,
            message=normalized_message,
            timestamp=normalized_timestamp,
        )


__all__ = (
    "ExecutionReport",
    "ExecutionReportFactory",
)