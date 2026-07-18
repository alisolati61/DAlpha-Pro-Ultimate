import math

import pytest

from src.risk.portfolio_guard import (
    PortfolioGuard,
    PortfolioState,
)


@pytest.fixture
def guard():

    return PortfolioGuard(
        max_positions=5,
        max_portfolio_risk=0.05,
        max_daily_loss=0.03,
        max_margin_usage=0.80,
    )


def make_state(**overrides):

    data = {
        "balance": 10_000.0,
        "equity": 10_000.0,
        "used_margin": 1_000.0,
        "open_positions": 2,
        "daily_loss": 0.01,
        "total_risk": 0.02,
    }

    data.update(overrides)

    return PortfolioState(**data)


def test_valid_portfolio_is_approved(guard):

    assert guard.validate(
        make_state()
    ) is True


def test_max_positions_is_rejected(guard):

    state = make_state(
        open_positions=5,
    )

    assert guard.validate(state) is False


def test_excessive_portfolio_risk_is_rejected(guard):

    state = make_state(
        total_risk=0.0501,
    )

    assert guard.validate(state) is False


def test_excessive_daily_loss_is_rejected(guard):

    state = make_state(
        daily_loss=0.0301,
    )

    assert guard.validate(state) is False


def test_excessive_margin_usage_is_rejected(guard):

    state = make_state(
        used_margin=8_001.0,
    )

    assert guard.validate(state) is False


def test_zero_balance_is_rejected(guard):

    state = make_state(
        balance=0,
    )

    approved, reason = guard.validate_with_reason(state)

    assert approved is False

    assert reason == (
        "Balance must be greater than zero."
    )


@pytest.mark.parametrize(
    "balance",
    [
        -1,
        math.nan,
        math.inf,
        -math.inf,
    ],
)
def test_invalid_balance_is_rejected(
    guard,
    balance,
):

    state = make_state(
        balance=balance,
    )

    assert guard.validate(state) is False


def test_negative_equity_is_rejected(guard):

    state = make_state(
        equity=-1,
    )

    assert guard.validate(state) is False


@pytest.mark.parametrize(
    "open_positions",
    [
        -1,
        -10,
    ],
)
def test_negative_open_positions_are_rejected(
    guard,
    open_positions,
):

    state = make_state(
        open_positions=open_positions,
    )

    assert guard.validate(state) is False


@pytest.mark.parametrize(
    "daily_loss",
    [
        -0.01,
        math.nan,
        math.inf,
    ],
)
def test_invalid_daily_loss_is_rejected(
    guard,
    daily_loss,
):

    state = make_state(
        daily_loss=daily_loss,
    )

    assert guard.validate(state) is False


@pytest.mark.parametrize(
    "total_risk",
    [
        -0.01,
        math.nan,
        math.inf,
    ],
)
def test_invalid_total_risk_is_rejected(
    guard,
    total_risk,
):

    state = make_state(
        total_risk=total_risk,
    )

    assert guard.validate(state) is False


@pytest.mark.parametrize(
    "used_margin",
    [
        -1,
        math.nan,
        math.inf,
    ],
)
def test_invalid_used_margin_is_rejected(
    guard,
    used_margin,
):

    state = make_state(
        used_margin=used_margin,
    )

    assert guard.validate(state) is False


def test_validate_with_reason_returns_success(
    guard,
):

    approved, reason = guard.validate_with_reason(
        make_state()
    )

    assert approved is True

    assert reason is None


def test_validate_with_reason_returns_failure_reason(
    guard,
):

    approved, reason = guard.validate_with_reason(
        make_state(
            total_risk=0.06,
        )
    )

    assert approved is False

    assert reason == (
        "Maximum portfolio risk exceeded."
    )


@pytest.mark.parametrize(
    "max_positions",
    [
        0,
        -1,
    ],
)
def test_invalid_max_positions(
    max_positions,
):

    with pytest.raises(
        ValueError,
    ):

        PortfolioGuard(
            max_positions=max_positions,
        )


@pytest.mark.parametrize(
    "ratio",
    [
        -0.01,
        1.01,
        math.nan,
        math.inf,
    ],
)
def test_invalid_risk_configuration(
    ratio,
):

    with pytest.raises(
        ValueError,
    ):

        PortfolioGuard(
            max_portfolio_risk=ratio,
        )


def test_invalid_max_positions_type():

    with pytest.raises(
        TypeError,
    ):

        PortfolioGuard(
            max_positions=5.5,
        )


def test_result_types(guard):

    approved, reason = guard.validate_with_reason(
        make_state()
    )

    assert isinstance(
        approved,
        bool,
    )

    assert reason is None