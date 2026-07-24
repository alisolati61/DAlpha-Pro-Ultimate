"""Portfolio-level risk controls for new-trade admission.

Thresholds use fractional notation:

- ``0.05`` means 5%;
- ``0.03`` means 3%;
- ``0.80`` means 80%.

A threshold is treated as a hard ceiling. A portfolio already at a configured
limit is rejected because a new trade would increase exposure beyond that
limit.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from numbers import Real


@dataclass(frozen=True, slots=True)
class PortfolioState:
    """Immutable portfolio snapshot supplied to the risk engine.

    Validation is intentionally performed by :class:`PortfolioGuard` rather
    than here. This preserves the public contract in which malformed external
    snapshots produce a rejected validation result instead of raising during
    snapshot construction.
    """

    balance: float
    equity: float
    used_margin: float
    open_positions: int
    daily_loss: float
    total_risk: float


@dataclass(frozen=True, slots=True)
class PortfolioValidationResult:
    """Immutable result of one portfolio-risk evaluation."""

    approved: bool
    reason: str = ""
    margin_usage: float | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.approved, bool):
            raise TypeError(
                "approved must be a bool"
            )

        if not isinstance(self.reason, str):
            raise TypeError(
                "reason must be a string"
            )

        reason = self.reason.strip()

        if self.approved:
            if reason:
                raise ValueError(
                    "approved result must not have a reason"
                )
        elif not reason:
            raise ValueError(
                "rejected result requires a reason"
            )

        margin_usage = self.margin_usage

        if margin_usage is not None:
            margin_usage = _validate_finite_number(
                margin_usage,
                "margin_usage",
            )

            if margin_usage < 0.0:
                raise ValueError(
                    "margin_usage cannot be negative"
                )

        object.__setattr__(
            self,
            "reason",
            reason,
        )
        object.__setattr__(
            self,
            "margin_usage",
            margin_usage,
        )

    @property
    def rejected(self) -> bool:
        """Return whether the portfolio failed validation."""

        return not self.approved


class PortfolioGuard:
    """Validate whether a portfolio may accept another trade."""

    __slots__ = (
        "max_daily_loss",
        "max_margin_usage",
        "max_portfolio_risk",
        "max_positions",
    )

    def __init__(
        self,
        max_positions: int = 5,
        max_portfolio_risk: float = 0.05,
        max_daily_loss: float = 0.03,
        max_margin_usage: float = 0.80,
    ) -> None:
        self.max_positions = _validate_positive_integer(
            max_positions,
            "max_positions",
        )
        self.max_portfolio_risk = _validate_ratio(
            max_portfolio_risk,
            "max_portfolio_risk",
        )
        self.max_daily_loss = _validate_ratio(
            max_daily_loss,
            "max_daily_loss",
        )
        self.max_margin_usage = _validate_ratio(
            max_margin_usage,
            "max_margin_usage",
        )

    def evaluate(
        self,
        state: PortfolioState,
    ) -> PortfolioValidationResult:
        """Return a detailed portfolio-risk decision.

        Invalid snapshots are rejected rather than raised, matching the
        historical ``validate_with_reason`` behavior.
        """

        if not isinstance(
            state,
            PortfolioState,
        ):
            return self._reject(
                "Invalid portfolio state."
            )

        balance = self._state_number(
            state.balance,
            "Balance",
        )

        if balance is None:
            return self._reject(
                "Balance must be a finite number."
            )

        if balance <= 0.0:
            return self._reject(
                "Balance must be greater than zero."
            )

        equity = self._state_number(
            state.equity,
            "Equity",
        )

        if equity is None:
            return self._reject(
                "Equity must be a finite number."
            )

        if equity <= 0.0:
            return self._reject(
                "Equity must be greater than zero."
            )

        open_positions = state.open_positions

        if (
            isinstance(open_positions, bool)
            or not isinstance(open_positions, int)
        ):
            return self._reject(
                "Open positions must be an integer."
            )

        if open_positions < 0:
            return self._reject(
                "Open positions cannot be negative."
            )

        if open_positions >= self.max_positions:
            return self._reject(
                "Maximum open positions reached."
            )

        daily_loss = self._state_number(
            state.daily_loss,
            "Daily loss",
        )

        if daily_loss is None:
            return self._reject(
                "Daily loss must be a finite number."
            )

        if daily_loss < 0.0:
            return self._reject(
                "Daily loss cannot be negative."
            )

        if daily_loss >= self.max_daily_loss:
            return self._reject(
                "Daily loss limit exceeded."
            )

        total_risk = self._state_number(
            state.total_risk,
            "Total risk",
        )

        if total_risk is None:
            return self._reject(
                "Total risk must be a finite number."
            )

        if total_risk < 0.0:
            return self._reject(
                "Total risk cannot be negative."
            )

        if total_risk >= self.max_portfolio_risk:
            return self._reject(
                "Maximum portfolio risk exceeded."
            )

        used_margin = self._state_number(
            state.used_margin,
            "Used margin",
        )

        if used_margin is None:
            return self._reject(
                "Used margin must be a finite number."
            )

        if used_margin < 0.0:
            return self._reject(
                "Used margin cannot be negative."
            )

        margin_usage = used_margin / balance

        if margin_usage >= self.max_margin_usage:
            return self._reject(
                "Maximum margin usage exceeded.",
                margin_usage=margin_usage,
            )

        return PortfolioValidationResult(
            approved=True,
            margin_usage=margin_usage,
        )

    def validate(
        self,
        state: PortfolioState,
    ) -> bool:
        """Return whether another trade is permitted."""

        return self.evaluate(
            state,
        ).approved

    def validate_with_reason(
        self,
        state: PortfolioState,
    ) -> tuple[bool, str | None]:
        """Return the historical ``(approved, reason)`` tuple."""

        result = self.evaluate(
            state,
        )

        return (
            result.approved,
            None if result.approved else result.reason,
        )

    def margin_usage(
        self,
        state: PortfolioState,
    ) -> float:
        """Return current used-margin ratio for a valid balance snapshot.

        This helper validates only ``balance`` and ``used_margin`` because the
        remaining portfolio fields are unrelated to this calculation.
        """

        if not isinstance(
            state,
            PortfolioState,
        ):
            raise TypeError(
                "state must be a PortfolioState."
            )

        balance = _validate_finite_number(
            state.balance,
            "balance",
        )

        if balance <= 0.0:
            raise ValueError(
                "Balance must be greater than zero."
            )

        used_margin = _validate_finite_number(
            state.used_margin,
            "used_margin",
        )

        if used_margin < 0.0:
            raise ValueError(
                "Used margin cannot be negative."
            )

        return float(
            used_margin / balance
        )

    def remaining_positions(
        self,
        state: PortfolioState,
    ) -> int:
        """Return remaining position slots, clamped to zero."""

        if not isinstance(
            state,
            PortfolioState,
        ):
            raise TypeError(
                "state must be a PortfolioState."
            )

        open_positions = state.open_positions

        if (
            isinstance(open_positions, bool)
            or not isinstance(open_positions, int)
        ):
            raise TypeError(
                "Open positions must be an integer."
            )

        if open_positions < 0:
            raise ValueError(
                "Open positions cannot be negative."
            )

        return max(
            self.max_positions - open_positions,
            0,
        )

    @staticmethod
    def _state_number(
        value: object,
        _label: str,
    ) -> float | None:
        try:
            return _validate_finite_number(
                value,
                "state value",
            )
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _reject(
        reason: str,
        *,
        margin_usage: float | None = None,
    ) -> PortfolioValidationResult:
        return PortfolioValidationResult(
            approved=False,
            reason=reason,
            margin_usage=margin_usage,
        )


def _validate_positive_integer(
    value: object,
    name: str,
) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
    ):
        raise TypeError(
            f"{name} must be an integer."
        )

    if value <= 0:
        raise ValueError(
            f"{name} must be greater than zero."
        )

    return value


def _validate_ratio(
    value: object,
    name: str,
) -> float:
    ratio = _validate_finite_number(
        value,
        name,
    )

    if not 0.0 <= ratio <= 1.0:
        raise ValueError(
            f"{name} must be between 0 and 1."
        )

    return ratio


def _validate_finite_number(
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

    return number


__all__ = (
    "PortfolioGuard",
    "PortfolioState",
    "PortfolioValidationResult",
)