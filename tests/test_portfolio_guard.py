"""Tests for production portfolio-level risk controls."""

from dataclasses import FrozenInstanceError
from math import inf, nan

import pytest

from src.risk.portfolio_guard import (
    PortfolioGuard,
    PortfolioState,
    PortfolioValidationResult,
)


@pytest.fixture
def guard() -> PortfolioGuard:
    return PortfolioGuard(
        max_positions=5,
        max_portfolio_risk=0.05,
        max_daily_loss=0.03,
        max_margin_usage=0.80,
    )


def make_state(
    **overrides: object,
) -> PortfolioState:
    data: dict[str, object] = {
        "balance": 10_000.0,
        "equity": 10_000.0,
        "used_margin": 1_000.0,
        "open_positions": 2,
        "daily_loss": 0.01,
        "total_risk": 0.02,
    }
    data.update(overrides)

    return PortfolioState(
        **data,  # type: ignore[arg-type]
    )


def test_default_configuration() -> None:
    guard = PortfolioGuard()

    assert guard.max_positions == 5
    assert guard.max_portfolio_risk == 0.05
    assert guard.max_daily_loss == 0.03
    assert guard.max_margin_usage == 0.80


def test_integer_ratios_are_normalized() -> None:
    guard = PortfolioGuard(
        max_portfolio_risk=1,
        max_daily_loss=1,
        max_margin_usage=1,
    )

    assert guard.max_portfolio_risk == 1.0
    assert guard.max_daily_loss == 1.0
    assert guard.max_margin_usage == 1.0


def test_valid_portfolio_is_approved(
    guard: PortfolioGuard,
) -> None:
    assert guard.validate(
        make_state()
    ) is True


def test_evaluate_returns_detailed_success(
    guard: PortfolioGuard,
) -> None:
    result = guard.evaluate(
        make_state()
    )

    assert result == PortfolioValidationResult(
        approved=True,
        margin_usage=0.1,
    )
    assert result.rejected is False


def test_validate_with_reason_returns_success(
    guard: PortfolioGuard,
) -> None:
    approved, reason = guard.validate_with_reason(
        make_state()
    )

    assert approved is True
    assert reason is None


def test_validate_return_type_is_exact_bool(
    guard: PortfolioGuard,
) -> None:
    assert type(
        guard.validate(
            make_state()
        )
    ) is bool


def test_max_positions_is_rejected(
    guard: PortfolioGuard,
) -> None:
    result = guard.evaluate(
        make_state(
            open_positions=5,
        )
    )

    assert result.approved is False
    assert result.reason == (
        "Maximum open positions reached."
    )


def test_positions_above_limit_are_rejected(
    guard: PortfolioGuard,
) -> None:
    assert guard.validate(
        make_state(
            open_positions=8,
        )
    ) is False


def test_daily_loss_at_limit_is_rejected(
    guard: PortfolioGuard,
) -> None:
    result = guard.evaluate(
        make_state(
            daily_loss=0.03,
        )
    )

    assert result.approved is False
    assert result.reason == (
        "Daily loss limit exceeded."
    )


def test_daily_loss_below_limit_is_allowed(
    guard: PortfolioGuard,
) -> None:
    assert guard.validate(
        make_state(
            daily_loss=0.029999,
        )
    ) is True


def test_portfolio_risk_at_limit_is_rejected(
    guard: PortfolioGuard,
) -> None:
    result = guard.evaluate(
        make_state(
            total_risk=0.05,
        )
    )

    assert result.approved is False
    assert result.reason == (
        "Maximum portfolio risk exceeded."
    )


def test_portfolio_risk_below_limit_is_allowed(
    guard: PortfolioGuard,
) -> None:
    assert guard.validate(
        make_state(
            total_risk=0.049999,
        )
    ) is True


def test_margin_usage_at_limit_is_rejected(
    guard: PortfolioGuard,
) -> None:
    result = guard.evaluate(
        make_state(
            used_margin=8_000.0,
        )
    )

    assert result.approved is False
    assert result.reason == (
        "Maximum margin usage exceeded."
    )
    assert result.margin_usage == 0.8


def test_margin_usage_below_limit_is_allowed(
    guard: PortfolioGuard,
) -> None:
    assert guard.validate(
        make_state(
            used_margin=7_999.0,
        )
    ) is True


def test_zero_used_margin_is_allowed(
    guard: PortfolioGuard,
) -> None:
    result = guard.evaluate(
        make_state(
            used_margin=0.0,
        )
    )

    assert result.approved is True
    assert result.margin_usage == 0.0


def test_zero_daily_loss_and_risk_are_allowed(
    guard: PortfolioGuard,
) -> None:
    assert guard.validate(
        make_state(
            daily_loss=0.0,
            total_risk=0.0,
        )
    ) is True


def test_margin_usage_helper(
    guard: PortfolioGuard,
) -> None:
    assert guard.margin_usage(
        make_state(
            used_margin=2_500.0,
        )
    ) == 0.25


def test_remaining_positions(
    guard: PortfolioGuard,
) -> None:
    assert guard.remaining_positions(
        make_state(
            open_positions=2,
        )
    ) == 3


def test_remaining_positions_is_clamped(
    guard: PortfolioGuard,
) -> None:
    assert guard.remaining_positions(
        make_state(
            open_positions=8,
        )
    ) == 0


def test_invalid_state_type_is_rejected(
    guard: PortfolioGuard,
) -> None:
    result = guard.evaluate(
        None,  # type: ignore[arg-type]
    )

    assert result == PortfolioValidationResult(
        approved=False,
        reason="Invalid portfolio state.",
    )


def test_validate_with_reason_invalid_state(
    guard: PortfolioGuard,
) -> None:
    approved, reason = guard.validate_with_reason(
        object(),  # type: ignore[arg-type]
    )

    assert approved is False
    assert reason == "Invalid portfolio state."


@pytest.mark.parametrize(
    "balance",
    [
        0,
        -1,
    ],
)
def test_non_positive_balance_is_rejected(
    guard: PortfolioGuard,
    balance: float,
) -> None:
    approved, reason = guard.validate_with_reason(
        make_state(
            balance=balance,
        )
    )

    assert approved is False
    assert reason == (
        "Balance must be greater than zero."
    )


@pytest.mark.parametrize(
    "balance",
    [
        nan,
        inf,
        -inf,
        True,
        False,
        "10000",
        None,
        object(),
    ],
)
def test_invalid_balance_is_rejected(
    guard: PortfolioGuard,
    balance: object,
) -> None:
    approved, reason = guard.validate_with_reason(
        make_state(
            balance=balance,
        )
    )

    assert approved is False
    assert reason == (
        "Balance must be a finite number."
    )


@pytest.mark.parametrize(
    "equity",
    [
        0,
        -1,
    ],
)
def test_non_positive_equity_is_rejected(
    guard: PortfolioGuard,
    equity: float,
) -> None:
    approved, reason = guard.validate_with_reason(
        make_state(
            equity=equity,
        )
    )

    assert approved is False
    assert reason == (
        "Equity must be greater than zero."
    )


@pytest.mark.parametrize(
    "equity",
    [
        nan,
        inf,
        -inf,
        True,
        False,
        "10000",
        None,
        object(),
    ],
)
def test_invalid_equity_is_rejected(
    guard: PortfolioGuard,
    equity: object,
) -> None:
    approved, reason = guard.validate_with_reason(
        make_state(
            equity=equity,
        )
    )

    assert approved is False
    assert reason == (
        "Equity must be a finite number."
    )


@pytest.mark.parametrize(
    "open_positions",
    [
        -1,
        -10,
    ],
)
def test_negative_positions_are_rejected(
    guard: PortfolioGuard,
    open_positions: int,
) -> None:
    approved, reason = guard.validate_with_reason(
        make_state(
            open_positions=open_positions,
        )
    )

    assert approved is False
    assert reason == (
        "Open positions cannot be negative."
    )


@pytest.mark.parametrize(
    "open_positions",
    [
        True,
        False,
        2.5,
        "2",
        None,
        object(),
    ],
)
def test_invalid_positions_type_is_rejected(
    guard: PortfolioGuard,
    open_positions: object,
) -> None:
    approved, reason = guard.validate_with_reason(
        make_state(
            open_positions=open_positions,
        )
    )

    assert approved is False
    assert reason == (
        "Open positions must be an integer."
    )


@pytest.mark.parametrize(
    "daily_loss",
    [
        -0.01,
        -1.0,
    ],
)
def test_negative_daily_loss_is_rejected(
    guard: PortfolioGuard,
    daily_loss: float,
) -> None:
    approved, reason = guard.validate_with_reason(
        make_state(
            daily_loss=daily_loss,
        )
    )

    assert approved is False
    assert reason == (
        "Daily loss cannot be negative."
    )


@pytest.mark.parametrize(
    "daily_loss",
    [
        nan,
        inf,
        -inf,
        True,
        False,
        "0.01",
        None,
        object(),
    ],
)
def test_invalid_daily_loss_is_rejected(
    guard: PortfolioGuard,
    daily_loss: object,
) -> None:
    approved, reason = guard.validate_with_reason(
        make_state(
            daily_loss=daily_loss,
        )
    )

    assert approved is False
    assert reason == (
        "Daily loss must be a finite number."
    )


@pytest.mark.parametrize(
    "total_risk",
    [
        -0.01,
        -1.0,
    ],
)
def test_negative_total_risk_is_rejected(
    guard: PortfolioGuard,
    total_risk: float,
) -> None:
    approved, reason = guard.validate_with_reason(
        make_state(
            total_risk=total_risk,
        )
    )

    assert approved is False
    assert reason == (
        "Total risk cannot be negative."
    )


@pytest.mark.parametrize(
    "total_risk",
    [
        nan,
        inf,
        -inf,
        True,
        False,
        "0.02",
        None,
        object(),
    ],
)
def test_invalid_total_risk_is_rejected(
    guard: PortfolioGuard,
    total_risk: object,
) -> None:
    approved, reason = guard.validate_with_reason(
        make_state(
            total_risk=total_risk,
        )
    )

    assert approved is False
    assert reason == (
        "Total risk must be a finite number."
    )


@pytest.mark.parametrize(
    "used_margin",
    [
        -1,
        -100.0,
    ],
)
def test_negative_used_margin_is_rejected(
    guard: PortfolioGuard,
    used_margin: float,
) -> None:
    approved, reason = guard.validate_with_reason(
        make_state(
            used_margin=used_margin,
        )
    )

    assert approved is False
    assert reason == (
        "Used margin cannot be negative."
    )


@pytest.mark.parametrize(
    "used_margin",
    [
        nan,
        inf,
        -inf,
        True,
        False,
        "1000",
        None,
        object(),
    ],
)
def test_invalid_used_margin_is_rejected(
    guard: PortfolioGuard,
    used_margin: object,
) -> None:
    approved, reason = guard.validate_with_reason(
        make_state(
            used_margin=used_margin,
        )
    )

    assert approved is False
    assert reason == (
        "Used margin must be a finite number."
    )


def test_validation_priority_balance_before_positions(
    guard: PortfolioGuard,
) -> None:
    result = guard.evaluate(
        make_state(
            balance=0,
            open_positions=5,
        )
    )

    assert result.reason == (
        "Balance must be greater than zero."
    )


def test_validation_priority_positions_before_daily_loss(
    guard: PortfolioGuard,
) -> None:
    result = guard.evaluate(
        make_state(
            open_positions=5,
            daily_loss=0.5,
        )
    )

    assert result.reason == (
        "Maximum open positions reached."
    )


def test_validation_priority_daily_loss_before_total_risk(
    guard: PortfolioGuard,
) -> None:
    result = guard.evaluate(
        make_state(
            daily_loss=0.5,
            total_risk=0.5,
        )
    )

    assert result.reason == (
        "Daily loss limit exceeded."
    )


@pytest.mark.parametrize(
    "max_positions",
    [
        0,
        -1,
    ],
)
def test_invalid_max_positions_value(
    max_positions: int,
) -> None:
    with pytest.raises(
        ValueError,
        match=(
            "max_positions must be "
            "greater than zero"
        ),
    ):
        PortfolioGuard(
            max_positions=max_positions,
        )


@pytest.mark.parametrize(
    "max_positions",
    [
        True,
        False,
        5.5,
        "5",
        None,
        object(),
    ],
)
def test_invalid_max_positions_type(
    max_positions: object,
) -> None:
    with pytest.raises(
        TypeError,
        match=(
            "max_positions must be "
            "an integer"
        ),
    ):
        PortfolioGuard(
            max_positions=max_positions,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "field",
    [
        "max_portfolio_risk",
        "max_daily_loss",
        "max_margin_usage",
    ],
)
@pytest.mark.parametrize(
    "value",
    [
        -0.01,
        1.01,
    ],
)
def test_ratio_configuration_outside_range(
    field: str,
    value: float,
) -> None:
    arguments: dict[str, object] = {
        "max_positions": 5,
        "max_portfolio_risk": 0.05,
        "max_daily_loss": 0.03,
        "max_margin_usage": 0.80,
    }
    arguments[field] = value

    with pytest.raises(
        ValueError,
        match="must be between 0 and 1",
    ):
        PortfolioGuard(
            **arguments,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "field",
    [
        "max_portfolio_risk",
        "max_daily_loss",
        "max_margin_usage",
    ],
)
@pytest.mark.parametrize(
    "value",
    [
        nan,
        inf,
        -inf,
    ],
)
def test_non_finite_ratio_configuration(
    field: str,
    value: float,
) -> None:
    arguments: dict[str, object] = {
        "max_positions": 5,
        "max_portfolio_risk": 0.05,
        "max_daily_loss": 0.03,
        "max_margin_usage": 0.80,
    }
    arguments[field] = value

    with pytest.raises(
        ValueError,
        match="must be finite",
    ):
        PortfolioGuard(
            **arguments,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "field",
    [
        "max_portfolio_risk",
        "max_daily_loss",
        "max_margin_usage",
    ],
)
@pytest.mark.parametrize(
    "value",
    [
        True,
        False,
        "0.5",
        None,
        object(),
    ],
)
def test_non_numeric_ratio_configuration(
    field: str,
    value: object,
) -> None:
    arguments: dict[str, object] = {
        "max_positions": 5,
        "max_portfolio_risk": 0.05,
        "max_daily_loss": 0.03,
        "max_margin_usage": 0.80,
    }
    arguments[field] = value

    with pytest.raises(
        TypeError,
        match="must be a number",
    ):
        PortfolioGuard(
            **arguments,  # type: ignore[arg-type]
        )


def test_zero_ratio_configuration_is_valid() -> None:
    guard = PortfolioGuard(
        max_portfolio_risk=0,
        max_daily_loss=0,
        max_margin_usage=0,
    )

    assert guard.max_portfolio_risk == 0.0
    assert guard.max_daily_loss == 0.0
    assert guard.max_margin_usage == 0.0


def test_portfolio_state_is_immutable() -> None:
    state = make_state()

    with pytest.raises(
        FrozenInstanceError,
    ):
        state.balance = 1.0  # type: ignore[misc]


def test_result_is_immutable() -> None:
    result = PortfolioValidationResult(
        approved=True,
        margin_usage=0.1,
    )

    with pytest.raises(
        FrozenInstanceError,
    ):
        result.approved = False  # type: ignore[misc]


def test_result_strips_reason() -> None:
    result = PortfolioValidationResult(
        approved=False,
        reason="  Rejected.  ",
    )

    assert result.reason == "Rejected."


@pytest.mark.parametrize(
    "approved",
    [
        1,
        "True",
        None,
    ],
)
def test_result_rejects_invalid_approved_type(
    approved: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="approved must be a bool",
    ):
        PortfolioValidationResult(
            approved=approved,  # type: ignore[arg-type]
            reason="Rejected.",
        )


def test_approved_result_rejects_reason() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "approved result must not "
            "have a reason"
        ),
    ):
        PortfolioValidationResult(
            approved=True,
            reason="Rejected.",
        )


def test_rejected_result_requires_reason() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "rejected result requires "
            "a reason"
        ),
    ):
        PortfolioValidationResult(
            approved=False,
        )


@pytest.mark.parametrize(
    "reason",
    [
        None,
        1,
        True,
    ],
)
def test_result_rejects_invalid_reason_type(
    reason: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="reason must be a string",
    ):
        PortfolioValidationResult(
            approved=False,
            reason=reason,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "margin_usage",
    [
        nan,
        inf,
        -inf,
    ],
)
def test_result_rejects_non_finite_margin_usage(
    margin_usage: float,
) -> None:
    with pytest.raises(
        ValueError,
        match="margin_usage must be finite",
    ):
        PortfolioValidationResult(
            approved=True,
            margin_usage=margin_usage,
        )


@pytest.mark.parametrize(
    "margin_usage",
    [
        True,
        "0.1",
        object(),
    ],
)
def test_result_rejects_non_numeric_margin_usage(
    margin_usage: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="margin_usage must be a number",
    ):
        PortfolioValidationResult(
            approved=True,
            margin_usage=margin_usage,  # type: ignore[arg-type]
        )


def test_result_rejects_negative_margin_usage() -> None:
    with pytest.raises(
        ValueError,
        match="margin_usage cannot be negative",
    ):
        PortfolioValidationResult(
            approved=True,
            margin_usage=-0.01,
        )


def test_margin_usage_helper_rejects_invalid_state(
    guard: PortfolioGuard,
) -> None:
    with pytest.raises(
        TypeError,
        match="state must be a PortfolioState",
    ):
        guard.margin_usage(
            None,  # type: ignore[arg-type]
        )


def test_margin_usage_helper_rejects_zero_balance(
    guard: PortfolioGuard,
) -> None:
    with pytest.raises(
        ValueError,
        match="Balance must be greater than zero",
    ):
        guard.margin_usage(
            make_state(
                balance=0,
            )
        )


def test_remaining_positions_rejects_bool(
    guard: PortfolioGuard,
) -> None:
    with pytest.raises(
        TypeError,
        match=(
            "Open positions must be "
            "an integer"
        ),
    ):
        guard.remaining_positions(
            make_state(
                open_positions=True,
            )
        )