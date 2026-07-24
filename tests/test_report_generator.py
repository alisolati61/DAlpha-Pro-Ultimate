"""Tests for validated human-readable backtest reports."""

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta, timezone

import pytest

from src.backtesting.report_generator import (
    BacktestReport,
    ReportGenerator,
)
from src.backtesting.statistics_engine import BacktestStatistics


def statistics(
    *,
    total_trades: int = 10,
    wins: int = 7,
    losses: int = 3,
    breakevens: int = 0,
    win_rate: float = 70.0,
    net_profit: float = 380.0,
) -> BacktestStatistics:
    if net_profit >= 0.0:
        gross_loss = 120.0
        gross_profit = round(gross_loss + net_profit, 2)
    else:
        gross_profit = 120.0
        gross_loss = round(gross_profit - net_profit, 2)

    average_win = (
        round(gross_profit / wins, 2)
        if wins
        else 0.0
    )
    average_loss = (
        round(gross_loss / losses, 2)
        if losses
        else 0.0
    )
    profit_factor = (
        round(gross_profit / gross_loss, 2)
        if gross_loss
        else 0.0
    )
    expectancy = (
        round(net_profit / total_trades, 2)
        if total_trades
        else 0.0
    )

    return BacktestStatistics(
        total_trades=total_trades,
        wins=wins,
        losses=losses,
        breakevens=breakevens,
        win_rate=win_rate,
        gross_profit=gross_profit,
        gross_loss=gross_loss,
        net_profit=net_profit,
        average_win=average_win,
        average_loss=average_loss,
        profit_factor=profit_factor,
        expectancy=expectancy,
        max_drawdown=60.0,
        sharpe_ratio=1.52,
    )


def test_generates_report_with_attached_statistics() -> None:
    source = statistics()
    report = ReportGenerator().generate(source)

    assert isinstance(report, BacktestReport)
    assert report.statistics is source
    assert report.created_at.tzinfo is UTC


def test_summary_contains_all_core_metrics() -> None:
    report = ReportGenerator().generate(statistics())

    assert report.summary == (
        "Trades: 10 | Wins: 7 | Losses: 3 | Breakevens: 0 | "
        "WinRate: 70.00% | Net Profit: 380.00 | "
        "Profit Factor: 4.17 | Max Drawdown: 60.00 | "
        "Sharpe: 1.5200"
    )


def test_summary_formats_negative_profit() -> None:
    report = ReportGenerator().generate(
        statistics(net_profit=-25.5)
    )

    assert "Net Profit: -25.50" in report.summary


def test_custom_clock_is_used() -> None:
    created_at = datetime(2026, 7, 24, 10, 30, tzinfo=UTC)

    report = ReportGenerator(
        clock=lambda: created_at,
    ).generate(
        statistics(),
    )

    assert report.created_at == created_at


def test_non_utc_clock_value_is_normalized_to_utc() -> None:
    offset = timezone(
        timedelta(
            hours=3,
            minutes=30,
        )
    )

    local_time = datetime(
        2026,
        7,
        24,
        14,
        0,
        tzinfo=offset,
    )

    report = ReportGenerator(
        clock=lambda: local_time,
    ).generate(
        statistics(),
    )

    assert report.created_at == datetime(
        2026,
        7,
        24,
        10,
        30,
        tzinfo=UTC,
    )

    assert report.created_at.tzinfo is UTC


def test_generator_rejects_non_callable_clock() -> None:
    with pytest.raises(
        TypeError,
        match="clock must be callable or None",
    ):
        ReportGenerator(
            clock=1,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "value",
    [
        None,
        object(),
        1,
        "statistics",
    ],
)
def test_generate_rejects_invalid_statistics(
    value: object,
) -> None:
    with pytest.raises(
        TypeError,
        match=(
            "statistics must be a "
            "BacktestStatistics instance"
        ),
    ):
        ReportGenerator().generate(
            value,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "value",
    [
        None,
        object(),
        "2026-07-24",
        1,
    ],
)
def test_clock_must_return_datetime(
    value: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="clock result must be a datetime",
    ):
        ReportGenerator(
            clock=lambda: value,  # type: ignore[return-value]
        ).generate(
            statistics(),
        )


def test_clock_must_return_timezone_aware_datetime() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "clock result must be "
            "timezone-aware"
        ),
    ):
        ReportGenerator(
            clock=lambda: datetime(
                2026,
                7,
                24,
                10,
                30,
            )
        ).generate(
            statistics(),
        )


def test_report_profitable_property() -> None:
    report = ReportGenerator().generate(
        statistics(
            net_profit=1.0,
        )
    )

    assert report.profitable is True
    assert report.unprofitable is False
    assert report.flat is False


def test_report_unprofitable_property() -> None:
    report = ReportGenerator().generate(
        statistics(
            net_profit=-1.0,
        )
    )

    assert report.profitable is False
    assert report.unprofitable is True
    assert report.flat is False


def test_report_flat_property() -> None:
    report = ReportGenerator().generate(
        statistics(
            net_profit=0.0,
        )
    )

    assert report.profitable is False
    assert report.unprofitable is False
    assert report.flat is True


def test_report_normalizes_direct_creation_time_to_utc() -> None:
    offset = timezone(
        timedelta(
            hours=-4,
        )
    )

    report = BacktestReport(
        created_at=datetime(
            2026,
            7,
            24,
            8,
            0,
            tzinfo=offset,
        ),
        statistics=statistics(),
        summary="valid summary",
    )

    assert report.created_at == datetime(
        2026,
        7,
        24,
        12,
        0,
        tzinfo=UTC,
    )


@pytest.mark.parametrize(
    "value",
    [
        None,
        1,
        "time",
        object(),
    ],
)
def test_report_rejects_non_datetime_created_at(
    value: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="created_at must be a datetime",
    ):
        BacktestReport(
            created_at=value,  # type: ignore[arg-type]
            statistics=statistics(),
            summary="valid",
        )


def test_report_rejects_naive_created_at() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "created_at must be "
            "timezone-aware"
        ),
    ):
        BacktestReport(
            created_at=datetime(
                2026,
                7,
                24,
                12,
                0,
            ),
            statistics=statistics(),
            summary="valid",
        )


@pytest.mark.parametrize(
    "value",
    [
        None,
        object(),
        1,
        "statistics",
    ],
)
def test_report_rejects_invalid_statistics(
    value: object,
) -> None:
    with pytest.raises(
        TypeError,
        match=(
            "statistics must be a "
            "BacktestStatistics instance"
        ),
    ):
        BacktestReport(
            created_at=datetime.now(UTC),
            statistics=value,  # type: ignore[arg-type]
            summary="valid",
        )


@pytest.mark.parametrize(
    "value",
    [
        None,
        object(),
        1,
        True,
    ],
)
def test_report_rejects_non_string_summary(
    value: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="summary must be a string",
    ):
        BacktestReport(
            created_at=datetime.now(UTC),
            statistics=statistics(),
            summary=value,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "value",
    [
        "",
        "   ",
        "\n\t",
    ],
)
def test_report_rejects_empty_summary(
    value: str,
) -> None:
    with pytest.raises(
        ValueError,
        match="summary must not be empty",
    ):
        BacktestReport(
            created_at=datetime.now(UTC),
            statistics=statistics(),
            summary=value,
        )


@pytest.mark.parametrize(
    "field",
    [
        "created_at",
        "statistics",
        "summary",
    ],
)
def test_report_is_immutable(
    field: str,
) -> None:
    report = ReportGenerator().generate(
        statistics(),
    )

    with pytest.raises(
        FrozenInstanceError,
    ):
        setattr(
            report,
            field,
            None,
        )