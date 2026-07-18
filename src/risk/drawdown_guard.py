from __future__ import annotations

import logging
import math
from dataclasses import dataclass


logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class DrawdownStatus:
    peak_balance: float
    current_balance: float
    drawdown: float
    allowed: bool


class DrawdownGuard:
    """
    Protects the portfolio against excessive drawdown.

    max_drawdown uses fractional notation:

        0.15 = 15%
        0.10 = 10%

    A drawdown equal to the configured limit is considered
    a breach and trading is not allowed.
    """

    def __init__(
        self,
        max_drawdown: float = 0.15,
    ) -> None:

        self._validate_ratio(
            max_drawdown,
            "max_drawdown",
        )

        if max_drawdown == 0:

            raise ValueError(
                "max_drawdown must be greater than zero."
            )

        self.max_drawdown = float(
            max_drawdown
        )

    # --------------------------------------------------

    @staticmethod
    def _validate_ratio(
        value: float,
        name: str,
    ) -> None:

        if not isinstance(
            value,
            (int, float),
        ):

            raise TypeError(
                f"{name} must be a number."
            )

        if not math.isfinite(value):

            raise ValueError(
                f"{name} must be finite."
            )

        if value < 0 or value > 1:

            raise ValueError(
                f"{name} must be between 0 and 1."
            )

    # --------------------------------------------------

    @staticmethod
    def _validate_balance(
        value: float,
        name: str,
    ) -> None:

        if not isinstance(
            value,
            (int, float),
        ):

            raise TypeError(
                f"{name} must be a number."
            )

        if not math.isfinite(value):

            raise ValueError(
                f"{name} must be finite."
            )

        if value < 0:

            raise ValueError(
                f"{name} cannot be negative."
            )

    # --------------------------------------------------

    def calculate_drawdown(
        self,
        peak_balance: float,
        current_balance: float,
    ) -> float:

        self._validate_balance(
            peak_balance,
            "peak_balance",
        )

        self._validate_balance(
            current_balance,
            "current_balance",
        )

        if peak_balance <= 0:

            raise ValueError(
                "Peak balance must be greater than zero."
            )

        drawdown = (

            peak_balance
            - current_balance

        ) / peak_balance

        return float(
            max(drawdown, 0.0)
        )

    # --------------------------------------------------

    def check(
        self,
        peak_balance: float,
        current_balance: float,
    ) -> DrawdownStatus:

        drawdown = self.calculate_drawdown(
            peak_balance,
            current_balance,
        )

        allowed = (
            drawdown
            < self.max_drawdown
        )

        if not allowed:

            logger.warning(
                "Maximum drawdown exceeded: %.2f%%",
                drawdown * 100,
            )

        return DrawdownStatus(

            peak_balance=float(
                peak_balance
            ),

            current_balance=float(
                current_balance
            ),

            drawdown=float(
                round(drawdown, 6)
            ),

            allowed=allowed,

        )

    # --------------------------------------------------

    def can_continue(
        self,
        peak_balance: float,
        current_balance: float,
    ) -> bool:

        return self.check(
            peak_balance,
            current_balance,
        ).allowed