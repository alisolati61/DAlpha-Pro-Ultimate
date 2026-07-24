"""Portfolio drawdown protection.

``DrawdownGuard`` compares the current portfolio balance with a historical
peak balance. Drawdown uses fractional notation:

- ``0.15`` means 15%;
- ``0.10`` means 10%.

A drawdown equal to the configured maximum is a breach, so trading is allowed
only while ``drawdown < max_drawdown``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from math import isclose, isfinite
from numbers import Real

logger = logging.getLogger(__name__)

_DRAW_DOWN_DECIMALS = 6
_DRAW_DOWN_TOLERANCE = 0.5 * 10 ** (-_DRAW_DOWN_DECIMALS)


@dataclass(frozen=True, slots=True)
class DrawdownStatus:
    """Immutable result of one drawdown evaluation."""

    peak_balance: float
    current_balance: float
    drawdown: float
    allowed: bool

    def __post_init__(self) -> None:
        peak_balance = _validate_positive_balance(
            "peak_balance",
            self.peak_balance,
        )
        current_balance = _validate_non_negative_balance(
            "current_balance",
            self.current_balance,
        )
        drawdown = _validate_ratio(
            "drawdown",
            self.drawdown,
            allow_zero=True,
        )

        if not isinstance(self.allowed, bool):
            raise TypeError(
                "allowed must be a bool"
            )

        expected_drawdown = _round_drawdown(
            _calculate_drawdown(
                peak_balance,
                current_balance,
            )
        )

        if not isclose(
            drawdown,
            expected_drawdown,
            rel_tol=0.0,
            abs_tol=_DRAW_DOWN_TOLERANCE,
        ):
            raise ValueError(
                "drawdown is inconsistent with balances"
            )

        object.__setattr__(
            self,
            "peak_balance",
            peak_balance,
        )
        object.__setattr__(
            self,
            "current_balance",
            current_balance,
        )
        object.__setattr__(
            self,
            "drawdown",
            drawdown,
        )

    @property
    def breached(self) -> bool:
        """Return whether this evaluation rejected further trading."""

        return not self.allowed

    @property
    def drawdown_percent(self) -> float:
        """Return drawdown as a percentage rounded to four decimals."""

        return _normalize_zero(
            round(
                self.drawdown * 100.0,
                4,
            )
        )

    @property
    def recovered_above_peak(self) -> bool:
        """Return whether current balance is above the supplied peak."""

        return self.current_balance > self.peak_balance


class DrawdownGuard:
    """Protect a portfolio against excessive peak-to-current drawdown."""

    __slots__ = ("max_drawdown",)

    def __init__(
        self,
        max_drawdown: float = 0.15,
    ) -> None:
        self.max_drawdown = _validate_ratio(
            "max_drawdown",
            max_drawdown,
            allow_zero=False,
        )

    @property
    def max_drawdown_percent(self) -> float:
        """Return the configured maximum drawdown as a percentage."""

        return _normalize_zero(
            round(
                self.max_drawdown * 100.0,
                4,
            )
        )

    def calculate_drawdown(
        self,
        peak_balance: float,
        current_balance: float,
    ) -> float:
        """Return fractional drawdown without rounding.

        A balance above the supplied peak produces zero drawdown.
        """

        peak = _validate_positive_balance(
            "peak_balance",
            peak_balance,
        )
        current = _validate_non_negative_balance(
            "current_balance",
            current_balance,
        )

        return _calculate_drawdown(
            peak,
            current,
        )

    def check(
        self,
        peak_balance: float,
        current_balance: float,
    ) -> DrawdownStatus:
        """Evaluate drawdown and return an immutable status."""

        peak = _validate_positive_balance(
            "peak_balance",
            peak_balance,
        )
        current = _validate_non_negative_balance(
            "current_balance",
            current_balance,
        )

        drawdown = _calculate_drawdown(
            peak,
            current,
        )
        allowed = drawdown < self.max_drawdown

        if not allowed:
            logger.warning(
                "Maximum drawdown reached or exceeded: %.2f%% "
                "(limit: %.2f%%)",
                drawdown * 100.0,
                self.max_drawdown * 100.0,
            )

        return DrawdownStatus(
            peak_balance=peak,
            current_balance=current,
            drawdown=_round_drawdown(drawdown),
            allowed=allowed,
        )

    def can_continue(
        self,
        peak_balance: float,
        current_balance: float,
    ) -> bool:
        """Return whether trading may continue."""

        return self.check(
            peak_balance,
            current_balance,
        ).allowed

    def remaining_drawdown(
        self,
        peak_balance: float,
        current_balance: float,
    ) -> float:
        """Return remaining fractional drawdown capacity.

        The result is clamped to zero after the configured limit is reached.
        """

        drawdown = self.calculate_drawdown(
            peak_balance,
            current_balance,
        )

        return _round_drawdown(
            max(
                self.max_drawdown - drawdown,
                0.0,
            )
        )


def _calculate_drawdown(
    peak_balance: float,
    current_balance: float,
) -> float:
    return float(
        max(
            (
                peak_balance
                - current_balance
            )
            / peak_balance,
            0.0,
        )
    )


def _validate_number(
    name: str,
    value: object,
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

    return number


def _validate_positive_balance(
    name: str,
    value: object,
) -> float:
    balance = _validate_number(
        name,
        value,
    )

    if balance <= 0.0:
        if name == "peak_balance":
            raise ValueError(
                "Peak balance must be greater than zero."
            )

        raise ValueError(
            f"{name} must be greater than zero."
        )

    return balance


def _validate_non_negative_balance(
    name: str,
    value: object,
) -> float:
    balance = _validate_number(
        name,
        value,
    )

    if balance < 0.0:
        raise ValueError(
            f"{name} cannot be negative."
        )

    return balance


def _validate_ratio(
    name: str,
    value: object,
    *,
    allow_zero: bool,
) -> float:
    ratio = _validate_number(
        name,
        value,
    )

    if not 0.0 <= ratio <= 1.0:
        raise ValueError(
            f"{name} must be between 0 and 1."
        )

    if not allow_zero and ratio == 0.0:
        raise ValueError(
            f"{name} must be greater than zero."
        )

    return ratio


def _round_drawdown(
    value: float,
) -> float:
    return _normalize_zero(
        round(
            float(value),
            _DRAW_DOWN_DECIMALS,
        )
    )


def _normalize_zero(
    value: float,
) -> float:
    if value == 0.0:
        return 0.0

    return value


__all__ = (
    "DrawdownGuard",
    "DrawdownStatus",
)