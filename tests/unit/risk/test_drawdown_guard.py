import math

import pytest

from src.risk.drawdown_guard import (
    DrawdownGuard,
    DrawdownStatus,
)


@pytest.fixture
def guard():
    return DrawdownGuard(
        max_drawdown=0.15,
    )


def test_no_drawdown():

    guard = DrawdownGuard()

    drawdown = guard.calculate_drawdown(
        peak_balance=10_000,
        current_balance=10_000,
    )

    assert drawdown == 0.0


def test_fifteen_percent_drawdown():

    guard = DrawdownGuard(
        max_drawdown=0.15,
    )

    status = guard.check(
        peak_balance=10_000,
        current_balance=8_500,
    )

    assert isinstance(
        status,
        DrawdownStatus,
    )

    assert status.drawdown == 0.15

    assert status.allowed is False


def test_drawdown_below_limit_is_allowed(
    guard,
):

    status = guard.check(
        peak_balance=10_000,
        current_balance=9_000,
    )

    assert status.drawdown == 0.1

    assert status.allowed is True


def test_drawdown_above_limit_is_rejected(
    guard,
):

    status = guard.check(
        peak_balance=10_000,
        current_balance=8_000,
    )

    assert status.drawdown == 0.2

    assert status.allowed is False


def test_recovery_above_peak_has_zero_drawdown(
    guard,
):

    drawdown = guard.calculate_drawdown(
        peak_balance=10_000,
        current_balance=12_000,
    )

    assert drawdown == 0.0


def test_can_continue_returns_true_below_limit(
    guard,
):

    assert guard.can_continue(
        peak_balance=10_000,
        current_balance=9_000,
    ) is True


def test_can_continue_returns_false_at_limit(
    guard,
):

    assert guard.can_continue(
        peak_balance=10_000,
        current_balance=8_500,
    ) is False


@pytest.mark.parametrize(
    "peak_balance",
    [
        0,
        -1,
        math.nan,
        math.inf,
        -math.inf,
    ],
)
def test_invalid_peak_balance(
    guard,
    peak_balance,
):

    with pytest.raises(
        (ValueError, TypeError),
    ):

        guard.calculate_drawdown(
            peak_balance=peak_balance,
            current_balance=9_000,
        )


@pytest.mark.parametrize(
    "current_balance",
    [
        -1,
        math.nan,
        math.inf,
        -math.inf,
    ],
)
def test_invalid_current_balance(
    guard,
    current_balance,
):

    with pytest.raises(
        (ValueError, TypeError),
    ):

        guard.calculate_drawdown(
            peak_balance=10_000,
            current_balance=current_balance,
        )


@pytest.mark.parametrize(
    "max_drawdown",
    [
        0,
        -0.01,
        1.01,
        math.nan,
        math.inf,
        -math.inf,
    ],
)
def test_invalid_max_drawdown(
    max_drawdown,
):

    with pytest.raises(
        (ValueError, TypeError),
    ):

        DrawdownGuard(
            max_drawdown=max_drawdown,
        )


def test_max_drawdown_one_is_valid():

    guard = DrawdownGuard(
        max_drawdown=1.0,
    )

    status = guard.check(
        peak_balance=10_000,
        current_balance=1,
    )

    assert status.allowed is True


def test_result_types(guard):

    status = guard.check(
        peak_balance=10_000,
        current_balance=9_000,
    )

    assert isinstance(
        status.peak_balance,
        float,
    )

    assert isinstance(
        status.current_balance,
        float,
    )

    assert isinstance(
        status.drawdown,
        float,
    )

    assert isinstance(
        status.allowed,
        bool,
    )


def test_drawdown_status_is_immutable(guard):

    status = guard.check(
        peak_balance=10_000,
        current_balance=9_000,
    )

    with pytest.raises(
        AttributeError,
    ):

        status.allowed = False