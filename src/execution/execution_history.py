from __future__ import annotations

from collections import deque

from src.execution.execution_report import (
    ExecutionReport,
)


class ExecutionHistory:
    """
    Bounded in-memory history of execution reports.

    The history keeps the newest reports up to
    ``max_size`` and automatically evicts the oldest
    report when the capacity is exceeded.
    """

    def __init__(
        self,
        max_size: int = 1000,
    ) -> None:

        if isinstance(
            max_size,
            bool,
        ):

            raise TypeError(
                "max_size must be an integer."
            )

        if not isinstance(
            max_size,
            int,
        ):

            raise TypeError(
                "max_size must be an integer."
            )

        if max_size <= 0:

            raise ValueError(
                "max_size must be greater than zero."
            )

        self._reports: deque[
            ExecutionReport
        ] = deque(
            maxlen=max_size
        )

    def add(
        self,
        report: ExecutionReport,
    ) -> None:

        if not isinstance(
            report,
            ExecutionReport,
        ):

            raise TypeError(
                "report must be an ExecutionReport."
            )

        self._reports.append(report)

    def latest(
        self,
    ) -> ExecutionReport | None:

        if not self._reports:

            return None

        return self._reports[-1]

    def all(
        self,
    ) -> list[ExecutionReport]:

        return list(self._reports)

    def clear(
        self,
    ) -> None:

        self._reports.clear()

    def __len__(
        self,
    ) -> int:

        return len(self._reports)

    @property
    def max_size(
        self,
    ) -> int:

        return self._reports.maxlen