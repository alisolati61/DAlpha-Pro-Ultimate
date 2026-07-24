"""Validated simulation of one historical long trade.

The simulator applies round-trip commission and slippage to a long trade.
Rates are decimal fractions, so ``0.001`` means ``0.1%``.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isclose, isfinite
from numbers import Real


_MONEY_DECIMALS = 2
_PERCENT_DECIMALS = 2


@dataclass(frozen=True, slots=True)
class TradeRequest:
    """Input required to simulate one historical long trade."""

    entry_price: float
    exit_price: float
    quantity: float
    commission: float = 0.0004
    slippage: float = 0.0002

    def __post_init__(self) -> None:
        entry_price = _validate_positive_number(
            "entry_price",
            self.entry_price,
        )

        exit_price = _validate_positive_number(
            "exit_price",
            self.exit_price,
        )

        quantity = _validate_non_negative_number(
            "quantity",
            self.quantity,
        )

        commission = _validate_rate(
            "commission",
            self.commission,
        )

        slippage = _validate_rate(
            "slippage",
            self.slippage,
        )

        object.__setattr__(
            self,
            "entry_price",
            entry_price,
        )

        object.__setattr__(
            self,
            "exit_price",
            exit_price,
        )

        object.__setattr__(
            self,
            "quantity",
            quantity,
        )

        object.__setattr__(
            self,
            "commission",
            commission,
        )

        object.__setattr__(
            self,
            "slippage",
            slippage,
        )

    @property
    def entry_value(self) -> float:
        """Return position value at entry before trading costs."""

        return self.entry_price * self.quantity

    @property
    def exit_value(self) -> float:
        """Return position value at exit before trading costs."""

        return self.exit_price * self.quantity

    @property
    def turnover(self) -> float:
        """Return total entry-plus-exit notional."""

        return (
            self.entry_value
            + self.exit_value
        )


@dataclass(frozen=True, slots=True)
class TradeSimulationResult:
    """Immutable result of one simulated historical trade."""

    gross_profit: float
    commission_paid: float
    slippage_cost: float
    net_profit: float
    return_percent: float

    def __post_init__(self) -> None:
        gross_profit = _validate_number(
            "gross_profit",
            self.gross_profit,
        )

        commission_paid = _validate_non_negative_number(
            "commission_paid",
            self.commission_paid,
        )

        slippage_cost = _validate_non_negative_number(
            "slippage_cost",
            self.slippage_cost,
        )

        net_profit = _validate_number(
            "net_profit",
            self.net_profit,
        )

        return_percent = _validate_number(
            "return_percent",
            self.return_percent,
        )

        expected_net_profit = _round_money(
            gross_profit
            - commission_paid
            - slippage_cost
        )

        if not isclose(
            net_profit,
            expected_net_profit,
            rel_tol=0.0,
            abs_tol=1e-9,
        ):
            raise ValueError(
                "net_profit must equal gross_profit minus trading costs"
            )

        object.__setattr__(
            self,
            "gross_profit",
            gross_profit,
        )

        object.__setattr__(
            self,
            "commission_paid",
            commission_paid,
        )

        object.__setattr__(
            self,
            "slippage_cost",
            slippage_cost,
        )

        object.__setattr__(
            self,
            "net_profit",
            net_profit,
        )

        object.__setattr__(
            self,
            "return_percent",
            return_percent,
        )

    @property
    def total_cost(self) -> float:
        """Return total simulated commission and slippage."""

        return _round_money(
            self.commission_paid
            + self.slippage_cost
        )

    @property
    def profitable(self) -> bool:
        return self.net_profit > 0.0

    @property
    def unprofitable(self) -> bool:
        return self.net_profit < 0.0

    @property
    def flat(self) -> bool:
        return self.net_profit == 0.0


class TradeSimulator:
    """Simulate one historical long trade with round-trip costs."""

    def simulate(
        self,
        trade: TradeRequest,
    ) -> TradeSimulationResult:
        """Return gross PnL, costs, net PnL, and percentage return."""

        if not isinstance(
            trade,
            TradeRequest,
        ):
            raise TypeError(
                "trade must be a TradeRequest instance"
            )

        gross_profit = _round_money(
            (
                trade.exit_price
                - trade.entry_price
            )
            * trade.quantity
        )

        commission_paid = _round_money(
            trade.turnover
            * trade.commission
        )

        slippage_cost = _round_money(
            trade.turnover
            * trade.slippage
        )

        net_profit = _round_money(
            gross_profit
            - commission_paid
            - slippage_cost
        )

        if trade.entry_value == 0.0:
            return_percent = 0.0
        else:
            return_percent = _round_percent(
                net_profit
                / trade.entry_value
                * 100.0
            )

        return TradeSimulationResult(
            gross_profit=gross_profit,
            commission_paid=commission_paid,
            slippage_cost=slippage_cost,
            net_profit=net_profit,
            return_percent=return_percent,
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
            f"{name} must be a real number"
        )

    number = float(value)

    if not isfinite(number):
        raise ValueError(
            f"{name} must be finite"
        )

    return number


def _validate_positive_number(
    name: str,
    value: object,
) -> float:
    number = _validate_number(
        name,
        value,
    )

    if number <= 0.0:
        raise ValueError(
            f"{name} must be greater than zero"
        )

    return number


def _validate_non_negative_number(
    name: str,
    value: object,
) -> float:
    number = _validate_number(
        name,
        value,
    )

    if number < 0.0:
        raise ValueError(
            f"{name} must be greater than or equal to zero"
        )

    return number


def _validate_rate(
    name: str,
    value: object,
) -> float:
    rate = _validate_number(
        name,
        value,
    )

    if not 0.0 <= rate <= 1.0:
        raise ValueError(
            f"{name} must be between 0.0 and 1.0"
        )

    return rate


def _round_money(
    value: float,
) -> float:
    rounded = float(
        round(
            value,
            _MONEY_DECIMALS,
        )
    )

    if rounded == 0.0:
        return 0.0

    return rounded


def _round_percent(
    value: float,
) -> float:
    rounded = float(
        round(
            value,
            _PERCENT_DECIMALS,
        )
    )

    if rounded == 0.0:
        return 0.0

    return rounded


__all__ = [
    "TradeRequest",
    "TradeSimulationResult",
    "TradeSimulator",
]