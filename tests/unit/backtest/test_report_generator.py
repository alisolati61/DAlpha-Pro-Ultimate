from src.backtesting.report_generator import (
    BacktestReport,
    ReportGenerator,
)
from src.backtesting.statistics_engine import (
    BacktestStatistics,
)


def sample_statistics():

    return BacktestStatistics(
        total_trades=10,
        wins=7,
        losses=3,
        win_rate=70.0,
        gross_profit=500.0,
        gross_loss=120.0,
        net_profit=380.0,
        average_win=71.43,
        average_loss=40.0,
        profit_factor=4.17,
        expectancy=38.0,
        max_drawdown=60.0,
        sharpe_ratio=1.52,
    )


def test_generate_report():

    generator = ReportGenerator()

    report = generator.generate(
        sample_statistics(),
    )

    assert isinstance(report, BacktestReport)


def test_summary_contains_trade_count():

    generator = ReportGenerator()

    report = generator.generate(
        sample_statistics(),
    )

    assert "Trades: 10" in report.summary


def test_summary_contains_profit():

    generator = ReportGenerator()

    report = generator.generate(
        sample_statistics(),
    )

    assert "380.00" in report.summary


def test_statistics_attached():

    generator = ReportGenerator()

    report = generator.generate(
        sample_statistics(),
    )

    assert report.statistics.total_trades == 10


def test_created_at_exists():

    generator = ReportGenerator()

    report = generator.generate(
        sample_statistics(),
    )

    assert report.created_at is not None


def test_result_types():

    generator = ReportGenerator()

    report = generator.generate(
        sample_statistics(),
    )

    assert isinstance(report.summary, str)

    assert isinstance(report.statistics, BacktestStatistics)