from __future__ import annotations

from dataclasses import dataclass
import math

from src.execution.execution_report import ExecutionReport


@dataclass(slots=True)
class PortfolioState:
    cash: float
    position_size: float
    average_price: float


class PortfolioSynchronizer:
    """
    Synchronizes portfolio state after successful executions.
    """

    def __init__(
        self,
        initial_cash: float = 10_000.0,
    ) -> None:

        self._state = PortfolioState(
            cash=self._validate_cash(
                initial_cash,
            ),
            position_size=0.0,
            average_price=0.0,
        )

    @staticmethod
    def _validate_cash(
        cash: float,
    ) -> float:

        if isinstance(
            cash,
            bool,
        ):

            raise TypeError(
                "cash must be a number."
            )

        if not isinstance(
            cash,
            (int, float),
        ):

            raise TypeError(
                "cash must be a number."
            )

        cash = float(cash)

        if not math.isfinite(
            cash,
        ):

            raise ValueError(
                "cash must be finite."
            )

        if cash < 0:

            raise ValueError(
                "cash cannot be negative."
            )

        return cash

    @staticmethod
    def _validate_report(
        report: ExecutionReport,
    ) -> None:

        if not isinstance(
            report,
            ExecutionReport,
        ):

            raise TypeError(
                "report must be an ExecutionReport."
            )

    @property
    def state(
        self,
    ) -> PortfolioState:

        return self._state

    def apply(
        self,
        report: ExecutionReport,
    ) -> None:

        self._validate_report(
            report,
        )

        if not report.success:

            return

        quantity = float(
            report.quantity,
        )

        executed_price = float(
            report.executed_price,
        )

        if quantity <= 0:

            raise ValueError(
                "Successful execution quantity "
                "must be greater than zero."
            )

        if not math.isfinite(
            quantity,
        ):

            raise ValueError(
                "Successful execution quantity "
                "must be finite."
            )

        if executed_price <= 0:

            raise ValueError(
                "Successful execution price "
                "must be greater than zero."
            )

        if not math.isfinite(
            executed_price,
        ):

            raise ValueError(
                "Successful execution price "
                "must be finite."
            )

        cost = (
            executed_price
            * quantity
        )

        previous_size = (
            self._state.position_size
        )

        previous_cost = (
            previous_size
            * self._state.average_price
        )

        new_size = (
            previous_size
            + quantity
        )

        self._state.cash = float(
            self._state.cash
            - cost
        )

        self._state.position_size = float(
            new_size
        )

        self._state.average_price = float(
            (
                previous_cost
                + cost
            )
            / new_size
        )

    def reset(
        self,
        cash: float = 10_000.0,
    ) -> None:

        self._state = PortfolioState(
            cash=self._validate_cash(
                cash,
            ),
            position_size=0.0,
            average_price=0.0,
        )