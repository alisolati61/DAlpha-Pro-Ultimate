import pytest

from src.risk.portfolio_guard import PortfolioGuard
from src.risk.portfolio_guard import PortfolioState


@pytest.fixture
def guard():
    return PortfolioGuard()


def test_valid_portfolio(guard):

    state = PortfolioState(
        balance=10000,
        equity=10100,
        used_margin=2000,
        open_positions=2,
        daily_loss=0.01,
        total_risk=0.03,
    )

    assert guard.validate(state)


def test_too_many_positions(guard):

    state = PortfolioState(
        balance=10000,
        equity=10000,
        used_margin=2000,
        open_positions=10,
        daily_loss=0.01,
        total_risk=0.03,
    )

    assert not guard.validate(state)


def test_daily_loss_limit(guard):

    state = PortfolioState(
        balance=10000,
        equity=9500,
        used_margin=2000,
        open_positions=2,
        daily_loss=0.05,
        total_risk=0.03,
    )

    assert not guard.validate(state)


def test_margin_limit(guard):

    state = PortfolioState(
        balance=10000,
        equity=10000,
        used_margin=9000,
        open_positions=2,
        daily_loss=0.01,
        total_risk=0.03,
    )

    assert not guard.validate(state)