"""Thread-safe execution-report portfolio synchronization.

The historical contract is preserved:

- successful reports increase one aggregate long position;
- failed reports do not change portfolio state;
- ``state`` returns the live mutable ``PortfolioState`` object;
- ``apply`` returns ``None``;
- ``reset`` restores an empty aggregate position.

Because ``ExecutionReport`` currently has no side field, this synchronizer
models acquisitions only. It does not infer SELL behavior from symbols,
messages, or order identifiers.

All arithmetic is validated before mutation. A successful execution that would
make cash negative is rejected.
"""

from __future__ import annotations

from collections.abc import Iterable
from copy import deepcopy
from dataclasses import dataclass
from math import isfinite
from numbers import Real
from threading import RLock

from src.execution.execution_report import ExecutionReport

_MAX_ORDER_ID_LENGTH = 200


@dataclass(slots=True)
class PortfolioState:
    """Mutable aggregate cash and long-position state."""

    cash: float
    position_size: float
    average_price: float

    @property
    def is_flat(self) -> bool:
        """Return whether no aggregate position is open."""

        return self.position_size == 0.0

    @property
    def position_cost(self) -> float:
        """Return aggregate cost basis."""

        value = self.position_size * self.average_price

        if not isfinite(value):
            raise ValueError(
                "position cost must be finite."
            )

        return float(value)


class PortfolioSynchronizer:
    """Synchronize aggregate portfolio state from execution reports."""

    __slots__ = (
        "_applied_order_ids",
        "_lock",
        "_state",
    )

    def __init__(
        self,
        initial_cash: float = 10_000.0,
    ) -> None:
        self._lock = RLock()
        self._state = self._empty_state(
            initial_cash
        )
        self._applied_order_ids: set[str] = set()

    @staticmethod
    def _validate_cash(
        cash: object,
    ) -> float:
        if (
            isinstance(cash, bool)
            or not isinstance(cash, Real)
        ):
            raise TypeError(
                "cash must be a number."
            )

        normalized = float(cash)

        if not isfinite(normalized):
            raise ValueError(
                "cash must be finite."
            )

        if normalized < 0.0:
            raise ValueError(
                "cash cannot be negative."
            )

        return normalized

    @staticmethod
    def _validate_report(
        report: object,
    ) -> ExecutionReport:
        if not isinstance(
            report,
            ExecutionReport,
        ):
            raise TypeError(
                "report must be an ExecutionReport."
            )

        if type(report.success) is not bool:
            raise TypeError(
                "report success must be a bool."
            )

        return report

    @staticmethod
    def _validate_execution_number(
        value: object,
        field_name: str,
    ) -> float:
        if (
            isinstance(value, bool)
            or not isinstance(value, Real)
        ):
            raise TypeError(
                "Successful execution "
                f"{field_name} must be a number."
            )

        normalized = float(value)

        if not isfinite(normalized):
            raise ValueError(
                "Successful execution "
                f"{field_name} must be finite."
            )

        if normalized <= 0.0:
            raise ValueError(
                "Successful execution "
                f"{field_name} must be greater than zero."
            )

        return normalized

    @staticmethod
    def _validate_order_id(
        order_id: object,
    ) -> str:
        if not isinstance(order_id, str):
            raise TypeError(
                "order_id must be a string."
            )

        normalized = order_id.strip()

        if not normalized:
            raise ValueError(
                "order_id cannot be empty."
            )

        if len(normalized) > _MAX_ORDER_ID_LENGTH:
            raise ValueError(
                "order_id must not exceed "
                f"{_MAX_ORDER_ID_LENGTH} characters."
            )

        return normalized

    @classmethod
    def _empty_state(
        cls,
        cash: object,
    ) -> PortfolioState:
        return PortfolioState(
            cash=cls._validate_cash(cash),
            position_size=0.0,
            average_price=0.0,
        )

    @staticmethod
    def _validate_current_state(
        state: PortfolioState,
    ) -> tuple[float, float, float]:
        cash = PortfolioSynchronizer._validate_cash(
            state.cash
        )
        position_size = (
            PortfolioSynchronizer
            ._validate_non_negative_finite(
                state.position_size,
                "position_size",
            )
        )
        average_price = (
            PortfolioSynchronizer
            ._validate_non_negative_finite(
                state.average_price,
                "average_price",
            )
        )

        if (
            position_size == 0.0
            and average_price != 0.0
        ):
            raise ValueError(
                "average_price must be zero "
                "when position_size is zero."
            )

        if (
            position_size > 0.0
            and average_price <= 0.0
        ):
            raise ValueError(
                "average_price must be greater than zero "
                "when position_size is positive."
            )

        return (
            cash,
            position_size,
            average_price,
        )

    @staticmethod
    def _validate_non_negative_finite(
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

        normalized = float(value)

        if not isfinite(normalized):
            raise ValueError(
                f"{name} must be finite."
            )

        if normalized < 0.0:
            raise ValueError(
                f"{name} cannot be negative."
            )

        return normalized

    @classmethod
    def _project_success(
        cls,
        state: PortfolioState,
        report: ExecutionReport,
    ) -> PortfolioState:
        cash, previous_size, average_price = (
            cls._validate_current_state(
                state
            )
        )
        quantity = cls._validate_execution_number(
            report.quantity,
            "quantity",
        )
        executed_price = (
            cls._validate_execution_number(
                report.executed_price,
                "price",
            )
        )

        cost = executed_price * quantity

        if not isfinite(cost):
            raise ValueError(
                "Successful execution cost "
                "must be finite."
            )

        if cost > cash:
            raise ValueError(
                "Insufficient cash for successful execution."
            )

        previous_cost = (
            previous_size * average_price
        )

        if not isfinite(previous_cost):
            raise ValueError(
                "Existing position cost must be finite."
            )

        new_size = previous_size + quantity

        if not isfinite(new_size):
            raise ValueError(
                "Updated position size must be finite."
            )

        combined_cost = previous_cost + cost

        if not isfinite(combined_cost):
            raise ValueError(
                "Updated position cost must be finite."
            )

        new_average_price = (
            combined_cost / new_size
        )
        new_cash = cash - cost

        if not isfinite(new_average_price):
            raise ValueError(
                "Updated average price must be finite."
            )

        if not isfinite(new_cash):
            raise ValueError(
                "Updated cash must be finite."
            )

        if new_cash < 0.0:
            raise ValueError(
                "cash cannot be negative."
            )

        return PortfolioState(
            cash=float(new_cash),
            position_size=float(new_size),
            average_price=float(
                new_average_price
            ),
        )

    @property
    def state(self) -> PortfolioState:
        """Return the live mutable state for legacy compatibility."""

        with self._lock:
            return self._state

    def snapshot(self) -> PortfolioState:
        """Return an independent state copy."""

        with self._lock:
            return deepcopy(self._state)

    def apply(
        self,
        report: ExecutionReport,
    ) -> None:
        """Apply one execution report atomically."""

        normalized_report = (
            self._validate_report(report)
        )

        if not normalized_report.success:
            return

        with self._lock:
            projected = self._project_success(
                self._state,
                normalized_report,
            )
            self._state.cash = projected.cash
            self._state.position_size = (
                projected.position_size
            )
            self._state.average_price = (
                projected.average_price
            )

    def apply_many(
        self,
        reports: Iterable[ExecutionReport],
    ) -> int:
        """Atomically apply multiple reports.

        Failed reports are validated but skipped. Any invalid or unaffordable
        successful report leaves the complete current state unchanged.

        Returns:
            Number of successful reports applied.
        """

        if (
            isinstance(
                reports,
                (
                    str,
                    bytes,
                    bytearray,
                ),
            )
            or not isinstance(reports, Iterable)
        ):
            raise TypeError(
                "reports must be an iterable "
                "of ExecutionReport objects."
            )

        normalized_reports = tuple(
            self._validate_report(report)
            for report in reports
        )

        with self._lock:
            projected = deepcopy(self._state)
            applied = 0

            for report in normalized_reports:
                if not report.success:
                    continue

                projected = self._project_success(
                    projected,
                    report,
                )
                applied += 1

            self._state.cash = projected.cash
            self._state.position_size = (
                projected.position_size
            )
            self._state.average_price = (
                projected.average_price
            )

        return applied

    def apply_once(
        self,
        report: ExecutionReport,
    ) -> bool:
        """Apply one successful report at most once by order ID.

        Failed reports are ignored and return ``False``. Repeated successful
        order IDs also return ``False`` without changing state.
        """

        normalized_report = (
            self._validate_report(report)
        )

        if not normalized_report.success:
            return False

        order_id = self._validate_order_id(
            normalized_report.order_id
        )

        with self._lock:
            if order_id in self._applied_order_ids:
                return False

            projected = self._project_success(
                self._state,
                normalized_report,
            )
            self._state.cash = projected.cash
            self._state.position_size = (
                projected.position_size
            )
            self._state.average_price = (
                projected.average_price
            )
            self._applied_order_ids.add(order_id)

        return True

    def has_applied(
        self,
        order_id: str,
    ) -> bool:
        """Return whether ``apply_once`` accepted an order ID."""

        normalized = self._validate_order_id(
            order_id
        )

        with self._lock:
            return (
                normalized
                in self._applied_order_ids
            )

    def applied_order_ids(
        self,
    ) -> tuple[str, ...]:
        """Return a deterministic snapshot of idempotent order IDs."""

        with self._lock:
            return tuple(
                sorted(self._applied_order_ids)
            )

    def position_cost(self) -> float:
        """Return aggregate position cost basis."""

        with self._lock:
            return self._state.position_cost

    def market_value(
        self,
        price: float,
    ) -> float:
        """Return aggregate position value at one mark price."""

        normalized_price = (
            self._validate_execution_number(
                price,
                "price",
            )
        )

        with self._lock:
            _, position_size, _ = (
                self._validate_current_state(
                    self._state
                )
            )

        value = position_size * normalized_price

        if not isfinite(value):
            raise ValueError(
                "Market value must be finite."
            )

        return float(value)

    def unrealized_pnl(
        self,
        price: float,
    ) -> float:
        """Return mark-to-cost unrealized PnL."""

        value = self.market_value(price)
        cost = self.position_cost()
        result = value - cost

        if not isfinite(result):
            raise ValueError(
                "Unrealized PnL must be finite."
            )

        return float(result)

    def equity(
        self,
        price: float,
    ) -> float:
        """Return cash plus aggregate market value."""

        value = self.market_value(price)

        with self._lock:
            cash, _, _ = (
                self._validate_current_state(
                    self._state
                )
            )

        result = cash + value

        if not isfinite(result):
            raise ValueError(
                "Equity must be finite."
            )

        return float(result)

    def reset(
        self,
        cash: float = 10_000.0,
    ) -> None:
        """Reset cash, position state, and idempotency history."""

        replacement = self._empty_state(cash)

        with self._lock:
            self._state = replacement
            self._applied_order_ids.clear()


__all__ = (
    "PortfolioState",
    "PortfolioSynchronizer",
)