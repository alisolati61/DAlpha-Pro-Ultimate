from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(slots=True)
class ValidationResult:
    approved: bool
    reason: Optional[str] = None


class PreTradeValidator:
    """
    Performs all pre-trade risk validations before an order
    is sent to the Execution Engine.
    """

    def __init__(
        self,
        max_position_size: float,
        max_leverage: float,
    ) -> None:

        self.max_position_size = max_position_size
        self.max_leverage = max_leverage

    def validate_position_size(
        self,
        position_size: float,
    ) -> ValidationResult:

        if position_size <= 0:
            return ValidationResult(
                False,
                "Position size must be greater than zero.",
            )

        if position_size > self.max_position_size:
            return ValidationResult(
                False,
                "Position size exceeds maximum allowed.",
            )

        return ValidationResult(True)

    def validate_leverage(
        self,
        leverage: float,
    ) -> ValidationResult:

        if leverage <= 0:
            return ValidationResult(
                False,
                "Leverage must be greater than zero.",
            )

        if leverage > self.max_leverage:
            return ValidationResult(
                False,
                "Leverage exceeds maximum allowed.",
            )

        return ValidationResult(True)

    def validate_stop_loss(
        self,
        entry_price: float,
        stop_loss: float,
    ) -> ValidationResult:

        if entry_price <= 0:
            return ValidationResult(
                False,
                "Invalid entry price.",
            )

        if stop_loss <= 0:
            return ValidationResult(
                False,
                "Invalid stop loss.",
            )

        if entry_price == stop_loss:
            return ValidationResult(
                False,
                "Stop loss cannot equal entry price.",
            )

        return ValidationResult(True)

    def validate(
        self,
        position_size: float,
        leverage: float,
        entry_price: float,
        stop_loss: float,
    ) -> ValidationResult:

        checks = [
            self.validate_position_size(position_size),
            self.validate_leverage(leverage),
            self.validate_stop_loss(
                entry_price,
                stop_loss,
            ),
        ]

        for result in checks:
            if not result.approved:
                return result

        return ValidationResult(True)