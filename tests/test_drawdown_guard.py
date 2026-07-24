"""Tests for validated portfolio drawdown protection."""

from dataclasses import FrozenInstanceError
from math import inf, nan

import pytest

from src.risk.drawdown_guard import (
    DrawdownGuard,
    DrawdownStatus,
)


@pytest.fixture
def guard() -> DrawdownGuard:
    return DrawdownGuard(
        max_drawdown=0.15,
    )


def test_default_configuration() -> None:
    guard = DrawdownGuard()

    assert guard.max_drawdown == 0.15
    assert guard.max_drawdown_percent == 15.0


def test_integer_configuration_is_normalized() -> None:
    guard = DrawdownGuard(
        max_drawdown=1,
    )

    assert guard.max_drawdown == 1.0
    assert isinstance(
        guard.max_drawdown,
        float,
    )


def test_no_drawdown() -> None:
    guard = DrawdownGuard()

    drawdown = guard.calculate_drawdown(
        peak_balance=10_000,
        current_balance=10_000,
    )

    assert drawdown == 0.0


def test_fifteen_percent_drawdown() -> None:
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
    assert status.breached is True


def test_drawdown_below_limit_is_allowed(
    guard: DrawdownGuard,
) -> None:
    status = guard.check(
        peak_balance=10_000,
        current_balance=9_000,
    )

    assert status.drawdown == 0.1
    assert status.drawdown_percent == 10.0
    assert status.allowed is True
    assert status.breached is False


def test_drawdown_above_limit_is_rejected(
    guard: DrawdownGuard,
) -> None:
    status = guard.check(
        peak_balance=10_000,
        current_balance=8_000,
    )

    assert status.drawdown == 0.2
    assert status.allowed is False


def test_recovery_above_peak_has_zero_drawdown(
    guard: DrawdownGuard,
) -> None:
    drawdown = guard.calculate_drawdown(
        peak_balance=10_000,
        current_balance=12_000,
    )

    assert drawdown == 0.0


def test_recovery_status_marks_above_peak(
    guard: DrawdownGuard,
) -> None:
    status = guard.check(
        peak_balance=10_000,
        current_balance=12_000,
    )

    assert status.drawdown == 0.0
    assert status.recovered_above_peak is True
    assert status.allowed is True


def test_equal_balance_is_not_recovered_above_peak(
    guard: DrawdownGuard,
) -> None:
    status = guard.check(
        peak_balance=10_000,
        current_balance=10_000,
    )

    assert status.recovered_above_peak is False


def test_zero_current_balance_is_total_drawdown(
    guard: DrawdownGuard,
) -> None:
    status = guard.check(
        peak_balance=10_000,
        current_balance=0,
    )

    assert status.drawdown == 1.0
    assert status.drawdown_percent == 100.0
    assert status.allowed is False


def test_can_continue_returns_true_below_limit(
    guard: DrawdownGuard,
) -> None:
    assert guard.can_continue(
        peak_balance=10_000,
        current_balance=9_000,
    ) is True


def test_can_continue_returns_false_at_limit(
    guard: DrawdownGuard,
) -> None:
    assert guard.can_continue(
        peak_balance=10_000,
        current_balance=8_500,
    ) is False


def test_max_drawdown_one_is_valid() -> None:
    guard = DrawdownGuard(
        max_drawdown=1.0,
    )

    status = guard.check(
        peak_balance=10_000,
        current_balance=1,
    )

    assert status.allowed is True


def test_max_drawdown_one_rejects_total_loss() -> None:
    guard = DrawdownGuard(
        max_drawdown=1.0,
    )

    status = guard.check(
        peak_balance=10_000,
        current_balance=0,
    )

    assert status.allowed is False


def test_calculation_is_not_rounded() -> None:
    guard = DrawdownGuard()

    result = guard.calculate_drawdown(
        peak_balance=3.0,
        current_balance=2.0,
    )

    assert result == pytest.approx(
        1.0 / 3.0,
    )
    assert result != 0.333333


def test_status_drawdown_is_rounded_to_six_decimals() -> None:
    status = DrawdownGuard(
        max_drawdown=0.5,
    ).check(
        peak_balance=3.0,
        current_balance=2.0,
    )

    assert status.drawdown == 0.333333


def test_remaining_drawdown_at_peak(
    guard: DrawdownGuard,
) -> None:
    assert guard.remaining_drawdown(
        peak_balance=10_000,
        current_balance=10_000,
    ) == 0.15


def test_remaining_drawdown_below_limit(
    guard: DrawdownGuard,
) -> None:
    assert guard.remaining_drawdown(
        peak_balance=10_000,
        current_balance=9_000,
    ) == 0.05


def test_remaining_drawdown_at_limit_is_zero(
    guard: DrawdownGuard,
) -> None:
    assert guard.remaining_drawdown(
        peak_balance=10_000,
        current_balance=8_500,
    ) == 0.0


def test_remaining_drawdown_above_limit_is_zero(
    guard: DrawdownGuard,
) -> None:
    assert guard.remaining_drawdown(
        peak_balance=10_000,
        current_balance=8_000,
    ) == 0.0


def test_breach_emits_warning(
    guard: DrawdownGuard,
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level("WARNING"):
        guard.check(
            peak_balance=10_000,
            current_balance=8_500,
        )

    assert (
        "Maximum drawdown reached or exceeded"
        in caplog.text
    )
    assert "15.00%" in caplog.text


def test_allowed_check_does_not_emit_warning(
    guard: DrawdownGuard,
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level("WARNING"):
        guard.check(
            peak_balance=10_000,
            current_balance=9_000,
        )

    assert caplog.text == ""


@pytest.mark.parametrize(
    "peak_balance",
    [
        0,
        -1,
    ],
)
def test_non_positive_peak_balance(
    guard: DrawdownGuard,
    peak_balance: float,
) -> None:
    with pytest.raises(
        ValueError,
        match=(
            "Peak balance must be greater "
            "than zero"
        ),
    ):
        guard.calculate_drawdown(
            peak_balance=peak_balance,
            current_balance=9_000,
        )


@pytest.mark.parametrize(
    "peak_balance",
    [
        nan,
        inf,
        -inf,
    ],
)
def test_non_finite_peak_balance(
    guard: DrawdownGuard,
    peak_balance: float,
) -> None:
    with pytest.raises(
        ValueError,
        match="peak_balance must be finite",
    ):
        guard.calculate_drawdown(
            peak_balance=peak_balance,
            current_balance=9_000,
        )


@pytest.mark.parametrize(
    "peak_balance",
    [
        True,
        False,
        "10000",
        None,
        object(),
    ],
)
def test_non_numeric_peak_balance(
    guard: DrawdownGuard,
    peak_balance: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="peak_balance must be a number",
    ):
        guard.calculate_drawdown(
            peak_balance=peak_balance,  # type: ignore[arg-type]
            current_balance=9_000,
        )


def test_negative_current_balance(
    guard: DrawdownGuard,
) -> None:
    with pytest.raises(
        ValueError,
        match="current_balance cannot be negative",
    ):
        guard.calculate_drawdown(
            peak_balance=10_000,
            current_balance=-1,
        )


@pytest.mark.parametrize(
    "current_balance",
    [
        nan,
        inf,
        -inf,
    ],
)
def test_non_finite_current_balance(
    guard: DrawdownGuard,
    current_balance: float,
) -> None:
    with pytest.raises(
        ValueError,
        match="current_balance must be finite",
    ):
        guard.calculate_drawdown(
            peak_balance=10_000,
            current_balance=current_balance,
        )


@pytest.mark.parametrize(
    "current_balance",
    [
        True,
        False,
        "9000",
        None,
        object(),
    ],
)
def test_non_numeric_current_balance(
    guard: DrawdownGuard,
    current_balance: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="current_balance must be a number",
    ):
        guard.calculate_drawdown(
            peak_balance=10_000,
            current_balance=current_balance,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "max_drawdown",
    [
        0,
        -0.01,
    ],
)
def test_non_positive_max_drawdown(
    max_drawdown: float,
) -> None:
    with pytest.raises(ValueError):
        DrawdownGuard(
            max_drawdown=max_drawdown,
        )


def test_max_drawdown_above_one() -> None:
    with pytest.raises(
        ValueError,
        match="max_drawdown must be between 0 and 1",
    ):
        DrawdownGuard(
            max_drawdown=1.01,
        )


@pytest.mark.parametrize(
    "max_drawdown",
    [
        nan,
        inf,
        -inf,
    ],
)
def test_non_finite_max_drawdown(
    max_drawdown: float,
) -> None:
    with pytest.raises(
        ValueError,
        match="max_drawdown must be finite",
    ):
        DrawdownGuard(
            max_drawdown=max_drawdown,
        )


@pytest.mark.parametrize(
    "max_drawdown",
    [
        True,
        False,
        "0.15",
        None,
        object(),
    ],
)
def test_non_numeric_max_drawdown(
    max_drawdown: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="max_drawdown must be a number",
    ):
        DrawdownGuard(
            max_drawdown=max_drawdown,  # type: ignore[arg-type]
        )


def test_result_types(
    guard: DrawdownGuard,
) -> None:
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


def test_drawdown_status_is_immutable(
    guard: DrawdownGuard,
) -> None:
    status = guard.check(
        peak_balance=10_000,
        current_balance=9_000,
    )

    with pytest.raises(
        FrozenInstanceError,
    ):
        status.allowed = False  # type: ignore[misc]


def test_status_normalizes_integer_balances() -> None:
    status = DrawdownStatus(
        peak_balance=10_000,
        current_balance=9_000,
        drawdown=0.1,
        allowed=True,
    )

    assert status.peak_balance == 10_000.0
    assert status.current_balance == 9_000.0
    assert isinstance(
        status.peak_balance,
        float,
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        (
            "peak_balance",
            "10000",
        ),
        (
            "current_balance",
            True,
        ),
        (
            "drawdown",
            None,
        ),
    ],
)
def test_status_rejects_non_numeric_values(
    field: str,
    value: object,
) -> None:
    arguments: dict[str, object] = {
        "peak_balance": 10_000.0,
        "current_balance": 9_000.0,
        "drawdown": 0.1,
        "allowed": True,
    }
    arguments[field] = value

    with pytest.raises(TypeError):
        DrawdownStatus(
            **arguments,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        (
            "peak_balance",
            nan,
        ),
        (
            "current_balance",
            inf,
        ),
        (
            "drawdown",
            -inf,
        ),
    ],
)
def test_status_rejects_non_finite_values(
    field: str,
    value: float,
) -> None:
    arguments = {
        "peak_balance": 10_000.0,
        "current_balance": 9_000.0,
        "drawdown": 0.1,
        "allowed": True,
    }
    arguments[field] = value

    with pytest.raises(ValueError):
        DrawdownStatus(**arguments)


@pytest.mark.parametrize(
    "value",
    [
        1,
        "True",
        None,
        object(),
    ],
)
def test_status_rejects_non_boolean_allowed(
    value: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="allowed must be a bool",
    ):
        DrawdownStatus(
            peak_balance=10_000.0,
            current_balance=9_000.0,
            drawdown=0.1,
            allowed=value,  # type: ignore[arg-type]
        )


def test_status_rejects_drawdown_outside_ratio() -> None:
    with pytest.raises(
        ValueError,
        match="drawdown must be between 0 and 1",
    ):
        DrawdownStatus(
            peak_balance=10_000.0,
            current_balance=9_000.0,
            drawdown=1.01,
            allowed=False,
        )


def test_status_rejects_inconsistent_drawdown() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "drawdown is inconsistent "
            "with balances"
        ),
    ):
        DrawdownStatus(
            peak_balance=10_000.0,
            current_balance=9_000.0,
            drawdown=0.2,
            allowed=True,
        )