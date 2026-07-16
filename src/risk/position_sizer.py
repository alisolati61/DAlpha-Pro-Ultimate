from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class PositionSizeResult:
    position_size: float
    risk_amount: float
    stop_distance: float


class PositionSizer:

    @staticmethod
    def calculate_position_size(
        balance: float,
        risk_percent: float,
        entry_price: float,
        stop_loss: float,
    ) -> PositionSizeResult:

        if balance <= 0:
            raise ValueError("Balance must be greater than zero.")

        if risk_percent <= 0:
            raise ValueError("Risk percent must be greater than zero.")

        stop_distance = abs(entry_price - stop_loss)

        if stop_distance <= 0:
            raise ValueError("Stop distance must be greater than zero.")

        risk_amount = balance * risk_percent

        position_size = risk_amount / stop_distance

        return PositionSizeResult(
            position_size=round(position_size, 8),
            risk_amount=round(risk_amount, 2),
            stop_distance=round(stop_distance, 8),
        )