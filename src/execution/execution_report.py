from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import math


@dataclass(slots=True)
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
    Creates standardized execution reports.
    """

    @staticmethod
    def success(
        order_id: str,
        symbol: str,
        quantity: float,
        price: float,
    ) -> ExecutionReport:

        if quantity <= 0:
            raise ValueError(
                "Successful execution quantity "
                "must be greater than zero."
            )

        if price <= 0:
            raise ValueError(
                "Successful execution price "
                "must be greater than zero."
            )

        if not math.isfinite(float(quantity)):
            raise ValueError(
                "Successful execution quantity "
                "must be finite."
            )

        if not math.isfinite(float(price)):
            raise ValueError(
                "Successful execution price "
                "must be finite."
            )

        return ExecutionReport(
            order_id=order_id,
            symbol=symbol,
            success=True,
            quantity=float(quantity),
            executed_price=float(price),
            message="Order executed.",
            timestamp=datetime.now(UTC),
        )

    @staticmethod
    def failed(
        symbol: str,
        message: str,
    ) -> ExecutionReport:

        return ExecutionReport(
            order_id="",
            symbol=symbol,
            success=False,
            quantity=0.0,
            executed_price=0.0,
            message=message,
            timestamp=datetime.now(UTC),
        )