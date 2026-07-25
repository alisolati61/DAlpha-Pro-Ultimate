"""Thread-safe bounded in-memory execution history.

The history preserves insertion order from oldest to newest and evicts the
oldest report when capacity is exceeded. Read methods return snapshots, so
callers cannot mutate internal state accidentally.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable, Iterator
from threading import RLock

from src.execution.execution_report import (
    ExecutionReport,
)

_MAX_LOOKUP_LENGTH = 200


class ExecutionHistory:
    """Bounded, thread-safe history of execution reports."""

    __slots__ = (
        "_lock",
        "_reports",
    )

    def __init__(
        self,
        max_size: int = 1000,
    ) -> None:
        if (
            isinstance(max_size, bool)
            or not isinstance(max_size, int)
        ):
            raise TypeError(
                "max_size must be an integer."
            )

        if max_size <= 0:
            raise ValueError(
                "max_size must be greater than zero."
            )

        self._lock = RLock()
        self._reports: deque[
            ExecutionReport
        ] = deque(
            maxlen=max_size,
        )

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

        return report

    @staticmethod
    def _normalize_lookup_string(
        value: object,
        field_name: str,
    ) -> str:
        if not isinstance(value, str):
            raise TypeError(
                f"{field_name} must be a string."
            )

        normalized = value.strip()

        if not normalized:
            raise ValueError(
                f"{field_name} cannot be empty."
            )

        if len(normalized) > _MAX_LOOKUP_LENGTH:
            raise ValueError(
                f"{field_name} must not exceed "
                f"{_MAX_LOOKUP_LENGTH} characters."
            )

        return normalized

    @staticmethod
    def _validate_positive_limit(
        limit: object,
    ) -> int:
        if (
            isinstance(limit, bool)
            or not isinstance(limit, int)
        ):
            raise TypeError(
                "limit must be an integer."
            )

        if limit <= 0:
            raise ValueError(
                "limit must be greater than zero."
            )

        return limit

    def add(
        self,
        report: ExecutionReport,
    ) -> None:
        """Append one report, evicting the oldest when full."""

        normalized_report = (
            self._validate_report(report)
        )

        with self._lock:
            self._reports.append(
                normalized_report
            )

    def extend(
        self,
        reports: Iterable[ExecutionReport],
    ) -> int:
        """Atomically append multiple reports.

        Every item is validated before internal state is changed. Therefore,
        one invalid item leaves the history untouched.

        Returns:
            Number of reports appended.
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
            or not isinstance(
                reports,
                Iterable,
            )
        ):
            raise TypeError(
                "reports must be an iterable "
                "of ExecutionReport objects."
            )

        validated_reports = tuple(
            self._validate_report(report)
            for report in reports
        )

        with self._lock:
            self._reports.extend(
                validated_reports
            )

        return len(validated_reports)

    def latest(
        self,
    ) -> ExecutionReport | None:
        """Return the newest report, or ``None`` when empty."""

        with self._lock:
            if not self._reports:
                return None

            return self._reports[-1]

    def all(
        self,
    ) -> list[ExecutionReport]:
        """Return an independent oldest-to-newest list snapshot."""

        with self._lock:
            return list(self._reports)

    def snapshot(
        self,
    ) -> tuple[ExecutionReport, ...]:
        """Return an immutable oldest-to-newest snapshot."""

        with self._lock:
            return tuple(self._reports)

    def recent(
        self,
        limit: int,
    ) -> list[ExecutionReport]:
        """Return up to ``limit`` newest reports in insertion order."""

        normalized_limit = (
            self._validate_positive_limit(
                limit
            )
        )

        with self._lock:
            if normalized_limit >= len(
                self._reports
            ):
                return list(self._reports)

            reports = list(self._reports)

        return reports[-normalized_limit:]

    def find_by_order_id(
        self,
        order_id: str,
    ) -> ExecutionReport | None:
        """Return the newest report with the requested order ID."""

        normalized_order_id = (
            self._normalize_lookup_string(
                order_id,
                "order_id",
            )
        )

        with self._lock:
            for report in reversed(
                self._reports
            ):
                if (
                    report.order_id
                    == normalized_order_id
                ):
                    return report

        return None

    def for_symbol(
        self,
        symbol: str,
        *,
        success: bool | None = None,
    ) -> list[ExecutionReport]:
        """Return reports for one symbol, optionally filtered by outcome."""

        normalized_symbol = (
            self._normalize_lookup_string(
                symbol,
                "symbol",
            )
        )

        if (
            success is not None
            and not isinstance(success, bool)
        ):
            raise TypeError(
                "success must be a bool or None."
            )

        with self._lock:
            reports = [
                report
                for report in self._reports
                if (
                    report.symbol
                    == normalized_symbol
                    and (
                        success is None
                        or report.success
                        is success
                    )
                )
            ]

        return reports

    def clear(
        self,
    ) -> None:
        """Remove every stored report."""

        with self._lock:
            self._reports.clear()

    def __len__(
        self,
    ) -> int:
        with self._lock:
            return len(self._reports)

    def __bool__(
        self,
    ) -> bool:
        with self._lock:
            return bool(self._reports)

    def __iter__(
        self,
    ) -> Iterator[ExecutionReport]:
        return iter(self.snapshot())

    @property
    def max_size(
        self,
    ) -> int:
        """Return the fixed history capacity."""

        maxlen = self._reports.maxlen

        if maxlen is None:
            raise RuntimeError(
                "Execution history is unexpectedly unbounded."
            )

        return maxlen

    @property
    def remaining_capacity(
        self,
    ) -> int:
        """Return unused capacity before the next eviction."""

        with self._lock:
            return self.max_size - len(
                self._reports
            )

    @property
    def is_full(
        self,
    ) -> bool:
        """Return whether the history is at capacity."""

        with self._lock:
            return (
                len(self._reports)
                == self.max_size
            )

    @property
    def successful_count(
        self,
    ) -> int:
        """Return the number of explicitly successful reports."""

        with self._lock:
            return sum(
                report.success is True
                for report in self._reports
            )

    @property
    def failed_count(
        self,
    ) -> int:
        """Return the number of explicitly failed reports."""

        with self._lock:
            return sum(
                report.success is False
                for report in self._reports
            )


__all__ = (
    "ExecutionHistory",
)