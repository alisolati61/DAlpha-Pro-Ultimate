from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import math
from numbers import Real


@dataclass(frozen=True, slots=True)
class ExecutionReport:
    order_id: str
    symbol: str
    success: bool
    quantity: float
    executed_price: float
    message: str
    timestamp: datetime


class ExecutionReportFactory:
    """
    Creates validated and immutable execution reports.
    """

    @staticmethod
    def _normalize_required_string(
        value: str,
        field_name: str,
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

        return normalized

    @staticmethod
    def _normalize_positive_number(
        value: Real,
        field_name: str,
    ) -> float:
        if isinstance(value, bool) or not isinstance(value, Real):
            raise TypeError(
                f"{field_name} must be a real number."
            )

        normalized = float(value)

        if not math.isfinite(normalized):
            raise ValueError(
                f"{field_name} must be finite."
            )

        if normalized <= 0:
            raise ValueError(
                f"{field_name} must be greater than zero."
            )

        return normalized

    @staticmethod
    def success(
        order_id: str,
        symbol: str,
        quantity: Real,
        price: Real,
    ) -> ExecutionReport:
        normalized_order_id = (
            ExecutionReportFactory._normalize_required_string(
                order_id,
                "order_id",
            )
        )

        normalized_symbol = (
            ExecutionReportFactory._normalize_required_string(
                symbol,
                "symbol",
            )
        )

        normalized_quantity = (
            ExecutionReportFactory._normalize_positive_number(
                quantity,
                "quantity",
            )
        )

        normalized_price = (
            ExecutionReportFactory._normalize_positive_number(
                price,
                "price",
            )
        )

        return ExecutionReport(
            order_id=normalized_order_id,
            symbol=normalized_symbol,
            success=True,
            quantity=normalized_quantity,
            executed_price=normalized_price,
            message="Order executed.",
            timestamp=datetime.now(UTC),
        )

    @staticmethod
    def failed(
        symbol: str,
        message: str,
    ) -> ExecutionReport:
        normalized_symbol = (
            ExecutionReportFactory._normalize_required_string(
                symbol,
                "symbol",
            )
        )

        normalized_message = (
            ExecutionReportFactory._normalize_required_string(
                message,
                "message",
            )
        )

        return ExecutionReport(
            order_id="",
            symbol=normalized_symbol,
            success=False,
            quantity=0.0,
            executed_price=0.0,
            message=normalized_message,
            timestamp=datetime.now(UTC),
        )