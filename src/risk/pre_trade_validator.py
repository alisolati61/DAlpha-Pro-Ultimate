from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ValidationResult:
    approved: bool
    reason: str | None = None

    @classmethod
    def approve(cls) -> ValidationResult:
        return cls(
            approved=True,
            reason=None,
        )

    @classmethod
    def reject(
        cls,
        reason: str,
    ) -> ValidationResult:
        return cls(
            approved=False,
            reason=reason,
        )


class PreTradeValidator:
    """
    Performs deterministic pre-trade validations.

    This validator checks generic constraints only:

    - position size
    - leverage
    - entry price
    - stop-loss price

    Direction-specific checks, such as whether a stop-loss
    is correctly placed below entry for a long position, should
    be performed by a higher-level order/risk policy that knows
    the trade side.
    """

    def __init__(
        self,
        max_position_size: float,
        max_leverage: float,
    ) -> None:

        self._validate_positive_finite(
            max_position_size,
            "max_position_size",
        )

        self._validate_positive_finite(
            max_leverage,
            "max_leverage",
        )

        self.max_position_size = float(
            max_position_size
        )

        self.max_leverage = float(
            max_leverage
        )

    # --------------------------------------------------

    @staticmethod
    def _validate_positive_finite(
        value: float,
        name: str,
    ) -> None:

        if not isinstance(value, (int, float)):

            raise TypeError(
                f"{name} must be a number."
            )

        if not math.isfinite(value):

            raise ValueError(
                f"{name} must be finite."
            )

        if value <= 0:

            raise ValueError(
                f"{name} must be greater than zero."
            )

    # --------------------------------------------------

    @staticmethod
    def _is_positive_finite(
        value: float,
    ) -> bool:

        return (

            isinstance(value, (int, float))

            and math.isfinite(value)

            and value > 0

        )

    # --------------------------------------------------

    def validate_position_size(
        self,
        position_size: float,
    ) -> ValidationResult:

        if not self._is_positive_finite(
            position_size
        ):

            return ValidationResult.reject(
                "Position size must be a finite number greater than zero."
            )

        if position_size > self.max_position_size:

            return ValidationResult.reject(
                "Position size exceeds maximum allowed."
            )

        return ValidationResult.approve()

    # --------------------------------------------------

    def validate_leverage(
        self,
        leverage: float,
    ) -> ValidationResult:

        if not self._is_positive_finite(
            leverage
        ):

            return ValidationResult.reject(
                "Leverage must be a finite number greater than zero."
            )

        if leverage > self.max_leverage:

            return ValidationResult.reject(
                "Leverage exceeds maximum allowed."
            )

        return ValidationResult.approve()

    # --------------------------------------------------

    def validate_stop_loss(
        self,
        entry_price: float,
        stop_loss: float,
    ) -> ValidationResult:

        if not self._is_positive_finite(
            entry_price
        ):

            return ValidationResult.reject(
                "Entry price must be a finite number greater than zero."
            )

        if not self._is_positive_finite(
            stop_loss
        ):

            return ValidationResult.reject(
                "Stop loss must be a finite number greater than zero."
            )

        if entry_price == stop_loss:

            return ValidationResult.reject(
                "Stop loss cannot equal entry price."
            )

        return ValidationResult.approve()

    # --------------------------------------------------

    def validate(
        self,
        position_size: float,
        leverage: float,
        entry_price: float,
        stop_loss: float,
    ) -> ValidationResult:

        result = self.validate_position_size(
            position_size
        )

        if not result.approved:

            return result

        result = self.validate_leverage(
            leverage
        )

        if not result.approved:

            return result

        result = self.validate_stop_loss(
            entry_price,
            stop_loss,
        )

        if not result.approved:

            return result

        return ValidationResult.approve()