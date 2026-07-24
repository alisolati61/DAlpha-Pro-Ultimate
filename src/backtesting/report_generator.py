"""Validated generation of human-readable backtest reports.

The report generator converts a completed ``BacktestStatistics`` instance into
an immutable report stamped with a timezone-aware UTC creation time. A custom
clock may be injected for deterministic tests or coordinated batch jobs.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from src.backtesting.statistics_engine import BacktestStatistics

Clock = Callable[[], datetime]


@dataclass(frozen=True, slots=True)
class BacktestReport:
    """Immutable human-readable report for one backtest result."""

    created_at: datetime
    statistics: BacktestStatistics
    summary: str

    def __post_init__(self) -> None:
        created_at = _normalize_utc_datetime(
            "created_at",
            self.created_at,
        )

        if not isinstance(self.statistics, BacktestStatistics):
            raise TypeError(
                "statistics must be a BacktestStatistics instance"
            )

        summary = _validate_non_empty_text(
            "summary",
            self.summary,
        )

        object.__setattr__(
            self,
            "created_at",
            created_at,
        )
        object.__setattr__(
            self,
            "summary",
            summary,
        )

    @property
    def profitable(self) -> bool:
        """Return whether the attached backtest made a net profit."""

        return self.statistics.net_profit > 0.0

    @property
    def unprofitable(self) -> bool:
        """Return whether the attached backtest made a net loss."""

        return self.statistics.net_profit < 0.0

    @property
    def flat(self) -> bool:
        """Return whether the attached backtest finished at zero net profit."""

        return self.statistics.net_profit == 0.0


class ReportGenerator:
    """Generate deterministic text reports from backtest statistics."""

    __slots__ = ("_clock",)

    def __init__(
        self,
        *,
        clock: Clock | None = None,
    ) -> None:
        if clock is not None and not callable(clock):
            raise TypeError("clock must be callable or None")

        self._clock: Clock = _utc_now if clock is None else clock

    def generate(
        self,
        statistics: BacktestStatistics,
    ) -> BacktestReport:
        """Create a UTC-stamped report without mutating ``statistics``."""

        if not isinstance(statistics, BacktestStatistics):
            raise TypeError(
                "statistics must be a BacktestStatistics instance"
            )

        created_at = _normalize_utc_datetime(
            "clock result",
            self._clock(),
        )

        summary = self._build_summary(statistics)

        return BacktestReport(
            created_at=created_at,
            statistics=statistics,
            summary=summary,
        )

    @staticmethod
    def _build_summary(
        statistics: BacktestStatistics,
    ) -> str:
        return (
            f"Trades: {statistics.total_trades} | "
            f"Wins: {statistics.wins} | "
            f"Losses: {statistics.losses} | "
            f"Breakevens: {statistics.breakevens} | "
            f"WinRate: {statistics.win_rate:.2f}% | "
            f"Net Profit: {statistics.net_profit:.2f} | "
            f"Profit Factor: {statistics.profit_factor:.2f} | "
            f"Max Drawdown: {statistics.max_drawdown:.2f} | "
            f"Sharpe: {statistics.sharpe_ratio:.4f}"
        )


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _normalize_utc_datetime(
    name: str,
    value: object,
) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError(f"{name} must be a datetime")

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")

    return value.astimezone(UTC)


def _validate_non_empty_text(
    name: str,
    value: object,
) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")

    if not value.strip():
        raise ValueError(f"{name} must not be empty")

    return value


__all__ = [
    "BacktestReport",
    "Clock",
    "ReportGenerator",
]