from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PositionSizeResult:
    """
    Result of a position-size calculation.

    risk_percent is expressed as a percentage value.

    Example:
        risk_percent=1.0
        means risking 1% of the account balance.
    """

    position_size: float
    risk_amount: float
    stop_distance: float


class PositionSizer:
    """
    Calculates position size from account risk.

    Formula:

        risk_amount = balance * (risk_percent / 100)

        position_size =
            risk_amount / stop_distance

    This class does not apply leverage, contract size,
    exchange precision, or fee calculations.
    """

    @staticmethod
    def calculate_position_size(
        balance: float,
        risk_percent: float,
        entry_price: float,
        stop_loss: float,
    ) -> PositionSizeResult:

        if balance <= 0:
            raise ValueError(
                "Balance must be greater than zero."
            )

        if risk_percent <= 0:
            raise ValueError(
                "Risk percent must be greater than zero."
            )

        if risk_percent > 100:
            raise ValueError(
                "Risk percent cannot exceed 100."
            )

        if entry_price <= 0:
            raise ValueError(
                "Entry price must be greater than zero."
            )

        if stop_loss <= 0:
            raise ValueError(
                "Stop-loss price must be greater than zero."
            )

        stop_distance = abs(
            float(entry_price) - float(stop_loss)
        )

        if stop_distance <= 0:
            raise ValueError(
                "Stop distance must be greater than zero."
            )

        risk_amount = (
            float(balance)
            * float(risk_percent)
            / 100.0
        )

        position_size = (
            risk_amount
            / stop_distance
        )

        return PositionSizeResult(
            position_size=float(
                round(position_size, 8)
            ),
            risk_amount=float(
                round(risk_amount, 8)
            ),
            stop_distance=float(
                round(stop_distance, 8)
            ),
        )