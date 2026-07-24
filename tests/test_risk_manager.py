"""Tests for the central account-level risk manager."""

from dataclasses import FrozenInstanceError
from fractions import Fraction
from math import inf, nan

import pytest

from src.risk.drawdown_guard import DrawdownGuard
from src.risk.kill_switch import KillSwitch
from src.risk.risk_manager import (
    RiskAssessment,
    RiskManager,
    RiskSettings,
    RiskStatus,
)


@pytest.fixture
def manager() -> RiskManager:
    return RiskManager(
        settings=RiskSettings(
            max_risk_per_trade=0.01,
            max_daily_loss=0.05,
            max_drawdown=0.15,
        )
    )


def test_default_manager_is_constructed() -> None:
    manager = RiskManager()

    assert isinstance(manager.settings, RiskSettings)
    assert isinstance(
        manager.drawdown_guard,
        DrawdownGuard,
    )
    assert isinstance(
        manager.kill_switch,
        KillSwitch,
    )


def test_default_settings() -> None:
    settings = RiskSettings()

    assert settings.max_risk_per_trade == 0.01
    assert settings.max_daily_loss == 0.05
    assert settings.max_drawdown == 0.15


def test_integer_settings_are_normalized() -> None:
    settings = RiskSettings(
        max_risk_per_trade=1,
        max_daily_loss=1,
        max_drawdown=1,
    )

    assert settings.max_risk_per_trade == 1.0
    assert settings.max_daily_loss == 1.0
    assert settings.max_drawdown == 1.0


def test_fraction_settings_are_supported() -> None:
    settings = RiskSettings(
        max_risk_per_trade=Fraction(1, 100),
        max_daily_loss=Fraction(5, 100),
        max_drawdown=Fraction(15, 100),
    )

    assert settings.max_risk_per_trade == 0.01
    assert settings.max_daily_loss == 0.05
    assert settings.max_drawdown == 0.15


def test_default_guard_matches_settings() -> None:
    manager = RiskManager(
        settings=RiskSettings(
            max_drawdown=0.2,
        )
    )

    assert manager.drawdown_guard.max_drawdown == 0.2


def test_calculate_risk_amount(
    manager: RiskManager,
) -> None:
    result = manager.calculate_risk_amount(
        10_000
    )

    assert result == 100.0
    assert type(result) is float


def test_large_finite_risk_amount_is_supported() -> None:
    manager = RiskManager(
        settings=RiskSettings(
            max_risk_per_trade=1.0,
        )
    )

    assert manager.calculate_risk_amount(
        1.79e308
    ) == 1.79e308


@pytest.mark.parametrize(
    "balance",
    [
        0,
        -1,
    ],
)
def test_non_positive_balance_is_rejected(
    manager: RiskManager,
    balance: float,
) -> None:
    with pytest.raises(
        ValueError,
        match="Balance must be greater than zero",
    ):
        manager.calculate_risk_amount(balance)


@pytest.mark.parametrize(
    "balance",
    [
        nan,
        inf,
        -inf,
    ],
)
def test_non_finite_balance_is_rejected(
    manager: RiskManager,
    balance: float,
) -> None:
    with pytest.raises(
        ValueError,
        match="balance must be finite",
    ):
        manager.calculate_risk_amount(balance)


@pytest.mark.parametrize(
    "balance",
    [
        True,
        False,
        "10000",
        None,
        object(),
    ],
)
def test_non_numeric_balance_is_rejected(
    manager: RiskManager,
    balance: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="balance must be a number",
    ):
        manager.calculate_risk_amount(
            balance  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    ("daily_loss", "expected"),
    [
        (
            0.0,
            True,
        ),
        (
            0.049,
            True,
        ),
        (
            0.05,
            False,
        ),
        (
            0.06,
            False,
        ),
    ],
)
def test_daily_loss_boundary(
    manager: RiskManager,
    daily_loss: float,
    expected: bool,
) -> None:
    assert manager.check_daily_loss(
        daily_loss
    ) is expected


def test_negative_daily_loss_is_rejected(
    manager: RiskManager,
) -> None:
    with pytest.raises(
        ValueError,
        match="Daily loss cannot be negative",
    ):
        manager.check_daily_loss(-0.01)


@pytest.mark.parametrize(
    "daily_loss",
    [
        nan,
        inf,
        -inf,
    ],
)
def test_non_finite_daily_loss_is_rejected(
    manager: RiskManager,
    daily_loss: float,
) -> None:
    with pytest.raises(
        ValueError,
        match="daily_loss must be finite",
    ):
        manager.check_daily_loss(daily_loss)


@pytest.mark.parametrize(
    "daily_loss",
    [
        True,
        False,
        "0.01",
        None,
        object(),
    ],
)
def test_non_numeric_daily_loss_is_rejected(
    manager: RiskManager,
    daily_loss: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="daily_loss must be a number",
    ):
        manager.check_daily_loss(
            daily_loss  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    ("daily_loss", "expected"),
    [
        (
            0.0,
            0.05,
        ),
        (
            0.02,
            0.03,
        ),
        (
            0.05,
            0.0,
        ),
        (
            0.10,
            0.0,
        ),
    ],
)
def test_remaining_daily_loss(
    manager: RiskManager,
    daily_loss: float,
    expected: float,
) -> None:
    assert manager.remaining_daily_loss(
        daily_loss
    ) == pytest.approx(expected)


@pytest.mark.parametrize(
    (
        "peak_balance",
        "current_balance",
        "expected",
    ),
    [
        (
            10_000,
            8_501,
            True,
        ),
        (
            10_000,
            8_500,
            False,
        ),
        (
            10_000,
            8_000,
            False,
        ),
        (
            0,
            9_000,
            False,
        ),
        (
            10_000,
            -1,
            False,
        ),
        (
            nan,
            9_000,
            False,
        ),
    ],
)
def test_drawdown_check_is_fail_closed(
    manager: RiskManager,
    peak_balance: float,
    current_balance: float,
    expected: bool,
) -> None:
    assert manager.check_drawdown(
        peak_balance,
        current_balance,
    ) is expected


def test_kill_switch_activation(
    manager: RiskManager,
) -> None:
    manager.activate_kill_switch(
        "Emergency shutdown"
    )

    assert manager.kill_switch.active is True
    assert manager.kill_switch.reason == (
        "Emergency shutdown"
    )


def test_kill_switch_deactivation(
    manager: RiskManager,
) -> None:
    manager.activate_kill_switch()
    manager.deactivate_kill_switch()

    assert manager.kill_switch.active is False


def test_invalid_activation_is_not_logged_as_success(
    manager: RiskManager,
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level("WARNING"):
        with pytest.raises(ValueError):
            manager.activate_kill_switch(" ")

    assert "Kill Switch Activated" not in caplog.text


def test_evaluate_ok(
    manager: RiskManager,
) -> None:
    result = manager.evaluate(
        daily_loss=0.01,
        peak_balance=10_000,
        current_balance=9_500,
    )

    assert result == RiskAssessment(
        allowed=True,
        status=RiskStatus.OK,
        daily_loss=0.01,
        drawdown=0.05,
    )


def test_evaluate_without_balances(
    manager: RiskManager,
) -> None:
    result = manager.evaluate(
        daily_loss=0.01,
    )

    assert result == RiskAssessment(
        allowed=True,
        status=RiskStatus.OK,
        daily_loss=0.01,
    )


def test_daily_loss_limit_assessment(
    manager: RiskManager,
) -> None:
    result = manager.evaluate(
        daily_loss=0.05,
        peak_balance=10_000,
        current_balance=9_500,
    )

    assert result.allowed is False
    assert result.status is (
        RiskStatus.DAILY_LOSS_LIMIT
    )
    assert result.reason == (
        "Daily loss limit reached or exceeded."
    )


def test_max_drawdown_assessment(
    manager: RiskManager,
) -> None:
    result = manager.evaluate(
        daily_loss=0.01,
        peak_balance=10_000,
        current_balance=8_500,
    )

    assert result.allowed is False
    assert result.status is RiskStatus.MAX_DRAWDOWN
    assert result.drawdown == 0.15


def test_invalid_drawdown_assessment(
    manager: RiskManager,
) -> None:
    result = manager.evaluate(
        daily_loss=0.01,
        peak_balance=0,
        current_balance=9_500,
    )

    assert result.status is RiskStatus.MAX_DRAWDOWN
    assert result.reason == (
        "Drawdown inputs are invalid."
    )


def test_kill_switch_has_first_priority(
    manager: RiskManager,
) -> None:
    manager.activate_kill_switch(
        "Emergency shutdown"
    )

    result = manager.evaluate(
        daily_loss=nan,
        peak_balance=0,
        current_balance=-1,
    )

    assert result.status is RiskStatus.KILL_SWITCH
    assert result.reason == "Emergency shutdown"


def test_daily_loss_has_priority_over_drawdown(
    manager: RiskManager,
) -> None:
    result = manager.evaluate(
        daily_loss=0.05,
        peak_balance=10_000,
        current_balance=8_000,
    )

    assert result.status is (
        RiskStatus.DAILY_LOSS_LIMIT
    )


@pytest.mark.parametrize(
    ("peak_balance", "current_balance"),
    [
        (
            10_000,
            None,
        ),
        (
            None,
            9_500,
        ),
    ],
)
def test_balances_must_be_provided_together(
    manager: RiskManager,
    peak_balance: float | None,
    current_balance: float | None,
) -> None:
    with pytest.raises(
        ValueError,
        match="must be provided together",
    ):
        manager.evaluate(
            daily_loss=0.01,
            peak_balance=peak_balance,
            current_balance=current_balance,
        )


@pytest.mark.parametrize(
    (
        "daily_loss",
        "peak_balance",
        "current_balance",
        "expected",
    ),
    [
        (
            0.01,
            10_000,
            9_500,
            RiskStatus.OK,
        ),
        (
            0.05,
            10_000,
            9_500,
            RiskStatus.DAILY_LOSS_LIMIT,
        ),
        (
            0.01,
            10_000,
            8_500,
            RiskStatus.MAX_DRAWDOWN,
        ),
    ],
)
def test_status(
    manager: RiskManager,
    daily_loss: float,
    peak_balance: float,
    current_balance: float,
    expected: RiskStatus,
) -> None:
    assert manager.status(
        daily_loss,
        peak_balance,
        current_balance,
    ) is expected


def test_status_kill_switch_priority(
    manager: RiskManager,
) -> None:
    manager.activate_kill_switch()

    assert manager.status(
        0.10,
        10_000,
        8_000,
    ) is RiskStatus.KILL_SWITCH


def test_can_trade_returns_exact_bool(
    manager: RiskManager,
) -> None:
    assert type(
        manager.can_trade(
            daily_loss=0.01,
        )
    ) is bool


def test_custom_dependencies_are_preserved() -> None:
    drawdown_guard = DrawdownGuard(
        max_drawdown=0.10,
    )
    kill_switch = KillSwitch()

    manager = RiskManager(
        settings=RiskSettings(
            max_drawdown=0.10,
        ),
        drawdown_guard=drawdown_guard,
        kill_switch=kill_switch,
    )

    assert manager.drawdown_guard is drawdown_guard
    assert manager.kill_switch is kill_switch


def test_invalid_settings_dependency() -> None:
    with pytest.raises(
        TypeError,
        match="settings must be a RiskSettings",
    ):
        RiskManager(
            settings=object(),  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    ("field", "dependency", "message"),
    [
        (
            "drawdown_guard",
            object(),
            "drawdown_guard must be a DrawdownGuard",
        ),
        (
            "kill_switch",
            object(),
            "kill_switch must be a KillSwitch",
        ),
    ],
)
def test_invalid_dependencies(
    field: str,
    dependency: object,
    message: str,
) -> None:
    arguments = {
        field: dependency,
    }

    with pytest.raises(
        TypeError,
        match=message,
    ):
        RiskManager(
            **arguments,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "field",
    [
        "max_risk_per_trade",
        "max_daily_loss",
        "max_drawdown",
    ],
)
@pytest.mark.parametrize(
    "value",
    [
        0,
        -0.01,
        1.01,
    ],
)
def test_invalid_settings_ratio(
    field: str,
    value: float,
) -> None:
    values: dict[str, object] = {
        "max_risk_per_trade": 0.01,
        "max_daily_loss": 0.05,
        "max_drawdown": 0.15,
    }
    values[field] = value

    with pytest.raises(
        ValueError,
        match="must be between 0 and 1",
    ):
        RiskSettings(
            **values,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "field",
    [
        "max_risk_per_trade",
        "max_daily_loss",
        "max_drawdown",
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
def test_non_finite_settings_ratio(
    field: str,
    value: float,
) -> None:
    values: dict[str, object] = {
        "max_risk_per_trade": 0.01,
        "max_daily_loss": 0.05,
        "max_drawdown": 0.15,
    }
    values[field] = value

    with pytest.raises(
        ValueError,
        match="must be finite",
    ):
        RiskSettings(
            **values,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "field",
    [
        "max_risk_per_trade",
        "max_daily_loss",
        "max_drawdown",
    ],
)
@pytest.mark.parametrize(
    "value",
    [
        True,
        False,
        "0.1",
        None,
        object(),
    ],
)
def test_non_numeric_settings_ratio(
    field: str,
    value: object,
) -> None:
    values: dict[str, object] = {
        "max_risk_per_trade": 0.01,
        "max_daily_loss": 0.05,
        "max_drawdown": 0.15,
    }
    values[field] = value

    with pytest.raises(
        TypeError,
        match="must be a number",
    ):
        RiskSettings(
            **values,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "field",
    [
        "max_risk_per_trade",
        "max_daily_loss",
        "max_drawdown",
    ],
)
def test_manager_revalidates_mutated_settings(
    field: str,
) -> None:
    settings = RiskSettings()
    object.__setattr__(settings, field, 0)

    with pytest.raises(ValueError):
        RiskManager(settings=settings)


def test_risk_settings_are_immutable() -> None:
    settings = RiskSettings()

    with pytest.raises(FrozenInstanceError):
        settings.max_drawdown = 0.20  # type: ignore[misc]


def test_risk_status_is_string_enum() -> None:
    assert RiskStatus.OK.value == "OK"
    assert str(RiskStatus.OK.value) == "OK"


def test_assessment_is_immutable() -> None:
    result = RiskAssessment(
        allowed=True,
        status=RiskStatus.OK,
    )

    with pytest.raises(FrozenInstanceError):
        result.allowed = False  # type: ignore[misc]


def test_assessment_blocked_property() -> None:
    result = RiskAssessment(
        allowed=False,
        status=RiskStatus.KILL_SWITCH,
        reason="Emergency",
    )

    assert result.blocked is True


@pytest.mark.parametrize(
    "allowed",
    [
        1,
        "True",
        None,
    ],
)
def test_assessment_rejects_non_bool_allowed(
    allowed: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="allowed must be a bool",
    ):
        RiskAssessment(
            allowed=allowed,  # type: ignore[arg-type]
            status=RiskStatus.OK,
        )


def test_assessment_rejects_invalid_status() -> None:
    with pytest.raises(
        TypeError,
        match="status must be a RiskStatus",
    ):
        RiskAssessment(
            allowed=True,
            status="OK",  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    (
        "allowed",
        "status",
        "reason",
        "message",
    ),
    [
        (
            False,
            RiskStatus.OK,
            "",
            "OK assessment must be allowed",
        ),
        (
            True,
            RiskStatus.OK,
            "Unexpected",
            "OK assessment must not have a reason",
        ),
        (
            True,
            RiskStatus.KILL_SWITCH,
            "Emergency",
            "blocking assessment cannot be allowed",
        ),
        (
            False,
            RiskStatus.KILL_SWITCH,
            "",
            "blocking assessment requires a reason",
        ),
    ],
)
def test_assessment_invariants(
    allowed: bool,
    status: RiskStatus,
    reason: str,
    message: str,
) -> None:
    with pytest.raises(
        ValueError,
        match=message,
    ):
        RiskAssessment(
            allowed=allowed,
            status=status,
            reason=reason,
        )


def test_assessment_reason_is_stripped() -> None:
    result = RiskAssessment(
        allowed=False,
        status=RiskStatus.KILL_SWITCH,
        reason="  Emergency  ",
    )

    assert result.reason == "Emergency"


def test_assessment_reason_length_is_bounded() -> None:
    with pytest.raises(
        ValueError,
        match="reason must not exceed 500 characters",
    ):
        RiskAssessment(
            allowed=False,
            status=RiskStatus.KILL_SWITCH,
            reason="x" * 501,
        )


@pytest.mark.parametrize(
    "drawdown",
    [
        -0.01,
        1.01,
        nan,
        inf,
        -inf,
    ],
)
def test_assessment_rejects_invalid_drawdown(
    drawdown: float,
) -> None:
    with pytest.raises(ValueError):
        RiskAssessment(
            allowed=False,
            status=RiskStatus.MAX_DRAWDOWN,
            reason="Drawdown",
            drawdown=drawdown,
        )


@pytest.mark.parametrize(
    "daily_loss",
    [
        -0.01,
        nan,
        inf,
        -inf,
    ],
)
def test_assessment_rejects_invalid_daily_loss(
    daily_loss: float,
) -> None:
    with pytest.raises(ValueError):
        RiskAssessment(
            allowed=True,
            status=RiskStatus.OK,
            daily_loss=daily_loss,
        )