"""Risk-based position sizing.

``risk_percent`` uses percentage notation:

- ``1.0`` means 1% of account balance;
- ``0.5`` means 0.5% of account balance;
- ``100.0`` means the full account balance.

The calculation intentionally does not apply leverage, fees, contract
multipliers, lot-size rules, quantity steps, or exchange precision. Those
constraints belong to the order-normalization layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isclose, isfinite
from numbers import Real

_RESULT_DECIMALS = 8
_CONSISTENCY_REL_TOLERANCE = 1e-7
_CONSISTENCY_ABS_TOLERANCE = 1e-8


@dataclass(frozen=True, slots=True)
class PositionSizeResult:
    """Immutable output of a position-size calculation."""

    position_size: float
    risk_amount: float
    stop_distance: float

    def __post_init__(self) -> None:
        position_size = _validate_positive_finite(
            self.position_size,
            "position_size",
        )
        risk_amount = _validate_positive_finite(
            self.risk_amount,
            "risk_amount",
        )
        stop_distance = _validate_positive_finite(
            self.stop_distance,
            "stop_distance",
        )

        if not isclose(
            position_size * stop_distance,
            risk_amount,
            rel_tol=_CONSISTENCY_REL_TOLERANCE,
            abs_tol=_CONSISTENCY_ABS_TOLERANCE,
        ):
            raise ValueError(
                "position_size, stop_distance, and "
                "risk_amount are inconsistent."
            )

        object.__setattr__(
            self,
            "position_size",
            position_size,
        )
        object.__setattr__(
            self,
            "risk_amount",
            risk_amount,
        )
        object.__setattr__(
            self,
            "stop_distance",
            stop_distance,
        )

    @property
    def notional_per_price_unit(self) -> float:
        """Return the calculated quantity."""

        return self.position_size


class PositionSizer:
    """Calculate quantity from account balance and stop distance."""

    @staticmethod
    def calculate_position_size(
        balance: float,
        risk_percent: float,
        entry_price: float,
        stop_loss: float,
    ) -> PositionSizeResult:
        """Return a validated risk-based position size.

        Formula::

            risk_amount = balance * (risk_percent / 100)
            stop_distance = abs(entry_price - stop_loss)
            position_size = risk_amount / stop_distance
        """

        validated_balance = _validate_positive_finite(
            balance,
            "Balance",
        )
        validated_risk_percent = _validate_risk_percent(
            risk_percent,
        )
        validated_entry_price = _validate_positive_finite(
            entry_price,
            "Entry price",
        )
        validated_stop_loss = _validate_positive_finite(
            stop_loss,
            "Stop-loss price",
        )

        stop_distance = abs(
            validated_entry_price
            - validated_stop_loss
        )

        if stop_distance <= 0.0:
            raise ValueError(
                "Stop distance must be greater than zero."
            )

        risk_amount = (
            validated_balance
            * (
                validated_risk_percent
                / 100.0
            )
        )
        position_size = (
            risk_amount
            / stop_distance
        )

        if not isfinite(position_size):
            raise ValueError(
                "Position size calculation must be finite."
            )

        rounded_risk_amount = _round_result(
            risk_amount,
            "Risk amount",
        )
        rounded_stop_distance = _round_result(
            stop_distance,
            "Stop distance",
        )
        rounded_position_size = _round_result(
            position_size,
            "Position size",
        )

        return PositionSizeResult(
            position_size=rounded_position_size,
            risk_amount=rounded_risk_amount,
            stop_distance=rounded_stop_distance,
        )


def _validate_risk_percent(
    value: object,
) -> float:
    risk_percent = _validate_positive_finite(
        value,
        "Risk percent",
    )

    if risk_percent > 100.0:
        raise ValueError(
            "Risk percent cannot exceed 100."
        )

    return risk_percent


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

    number = float(value)

    if not isfinite(number):
        raise ValueError(
            f"{name} must be finite."
        )

    if number <= 0.0:
        raise ValueError(
            f"{name} must be greater than zero."
        )

    return number


def _round_result(
    value: float,
    name: str,
) -> float:
    rounded = float(
        round(
            value,
            _RESULT_DECIMALS,
        )
    )

    if rounded <= 0.0:
        raise ValueError(
            f"{name} is below supported precision."
        )

    return rounded


__all__ = (
    "PositionSizeResult",
    "PositionSizer",
)