from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from src.backtesting.statistics_engine import BacktestStatistics


@dataclass(slots=True)
class BacktestReport:

    created_at: datetime

    statistics: BacktestStatistics

    summary: str


class ReportGenerator:
    """
    Generates a human-readable backtest report.

    Future:
    - HTML Report
    - PDF Report
    - CSV Export
    - Excel Export
    """

    def generate(
        self,
        statistics: BacktestStatistics,
    ) -> BacktestReport:

        summary = (
            f"Trades: {statistics.total_trades} | "
            f"WinRate: {statistics.win_rate:.2f}% | "
            f"Net Profit: {statistics.net_profit:.2f}"
        )

        return BacktestReport(
            created_at=datetime.now(UTC),
            statistics=statistics,
            summary=summary,
        )