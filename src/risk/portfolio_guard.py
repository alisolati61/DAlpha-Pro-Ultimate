from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PortfolioState:
    balance: float
    equity: float
    used_margin: float
    open_positions: int
    daily_loss: float
    total_risk: float


class PortfolioGuard:
    """
    Portfolio-level risk controller.

    Thresholds use fractional values:

        0.05 = 5%
        0.03 = 3%
        0.80 = 80%

    The guard validates whether a new trade is allowed
    based on the current portfolio state.
    """

    def __init__(
        self,
        max_positions: int = 5,
        max_portfolio_risk: float = 0.05,
        max_daily_loss: float = 0.03,
        max_margin_usage: float = 0.80,
    ) -> None:

        if not isinstance(
            max_positions,
            int,
        ):

            raise TypeError(
                "max_positions must be an integer."
            )

        if max_positions <= 0:

            raise ValueError(
                "max_positions must be greater than zero."
            )

        self._validate_ratio(
            max_portfolio_risk,
            "max_portfolio_risk",
        )

        self._validate_ratio(
            max_daily_loss,
            "max_daily_loss",
        )

        self._validate_ratio(
            max_margin_usage,
            "max_margin_usage",
        )

        self.max_positions = max_positions

        self.max_portfolio_risk = float(
            max_portfolio_risk
        )

        self.max_daily_loss = float(
            max_daily_loss
        )

        self.max_margin_usage = float(
            max_margin_usage
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
    def _is_finite_number(
        value: float,
    ) -> bool:

        return (

            isinstance(
                value,
                (int, float),
            )

            and math.isfinite(value)

        )

    # --------------------------------------------------

    def validate(
        self,
        state: PortfolioState,
    ) -> bool:

        return self.validate_with_reason(
            state
        )[0]

    # --------------------------------------------------

    def validate_with_reason(
        self,
        state: PortfolioState,
    ) -> tuple[bool, str | None]:

        if not isinstance(
            state,
            PortfolioState,
        ):

            return (
                False,
                "Invalid portfolio state.",
            )

        if not self._is_finite_number(
            state.balance
        ):

            return (
                False,
                "Balance must be a finite number.",
            )

        if state.balance <= 0:

            return (
                False,
                "Balance must be greater than zero.",
            )

        if not self._is_finite_number(
            state.equity
        ):

            return (
                False,
                "Equity must be a finite number.",
            )

        if state.equity < 0:

            return (
                False,
                "Equity cannot be negative.",
            )

        if not isinstance(
            state.open_positions,
            int,
        ):

            return (
                False,
                "Open positions must be an integer.",
            )

        if state.open_positions < 0:

            return (
                False,
                "Open positions cannot be negative.",
            )

        if state.open_positions >= self.max_positions:

            return (
                False,
                "Maximum open positions reached.",
            )

        if not self._is_finite_number(
            state.daily_loss
        ):

            return (
                False,
                "Daily loss must be a finite number.",
            )

        if state.daily_loss < 0:

            return (
                False,
                "Daily loss cannot be negative.",
            )

        if state.daily_loss > self.max_daily_loss:

            return (
                False,
                "Daily loss limit exceeded.",
            )

        if not self._is_finite_number(
            state.total_risk
        ):

            return (
                False,
                "Total risk must be a finite number.",
            )

        if state.total_risk < 0:

            return (
                False,
                "Total risk cannot be negative.",
            )

        if state.total_risk > self.max_portfolio_risk:

            return (
                False,
                "Maximum portfolio risk exceeded.",
            )

        if not self._is_finite_number(
            state.used_margin
        ):

            return (
                False,
                "Used margin must be a finite number.",
            )

        if state.used_margin < 0:

            return (
                False,
                "Used margin cannot be negative.",
            )

        margin_usage = (
            state.used_margin
            / state.balance
        )

        if margin_usage > self.max_margin_usage:

            return (
                False,
                "Maximum margin usage exceeded.",
            )

        return (
            True,
            None,
        )