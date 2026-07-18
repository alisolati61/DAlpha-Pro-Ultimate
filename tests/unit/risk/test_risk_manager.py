import math

import pytest

from src.risk.drawdown_guard import DrawdownGuard
from src.risk.kill_switch import KillSwitch
from src.risk.risk_manager import (
    RiskManager,
    RiskSettings,
    RiskStatus,
)


@pytest.fixture
def manager():

    return RiskManager(
        settings=RiskSettings(
            max_risk_per_trade=0.01,
            max_daily_loss=0.05,
            max_drawdown=0.15,
        )
    )


def test_default_manager_is_constructed():

    manager = RiskManager()

    assert isinstance(
        manager.settings,
        RiskSettings,
    )

    assert isinstance(
        manager.drawdown_guard,
        DrawdownGuard,
    )

    assert isinstance(
        manager.kill_switch,
        KillSwitch,
    )


def test_calculate_risk_amount(manager):

    result = manager.calculate_risk_amount(
        10_000
    )

    assert result == 100.0

    assert isinstance(
        result,
        float,
    )


def test_calculate_risk_amount_with_zero_balance(
    manager,
):

    with pytest.raises(
        ValueError,
    ):

        manager.calculate_risk_amount(0)


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
    manager,
    balance,
):

    with pytest.raises(
        (ValueError, TypeError),
    ):

        manager.calculate_risk_amount(
            balance
        )


def test_daily_loss_below_limit_is_allowed(
    manager,
):

    assert manager.check_daily_loss(
        0.049
    ) is True


def test_daily_loss_at_limit_is_rejected(
    manager,
):

    assert manager.check_daily_loss(
        0.05
    ) is False


def test_daily_loss_above_limit_is_rejected(
    manager,
):

    assert manager.check_daily_loss(
        0.06
    ) is False


def test_negative_daily_loss_is_rejected(
    manager,
):

    with pytest.raises(
        ValueError,
    ):

        manager.check_daily_loss(
            -0.01
        )


@pytest.mark.parametrize(
    "daily_loss",
    [
        math.nan,
        math.inf,
        -math.inf,
    ],
)
def test_invalid_daily_loss_is_rejected(
    manager,
    daily_loss,
):

    with pytest.raises(
        (ValueError, TypeError),
    ):

        manager.check_daily_loss(
            daily_loss
        )


def test_drawdown_below_limit_is_allowed(
    manager,
):

    assert manager.check_drawdown(
        10_000,
        8_501,
    ) is True


def test_drawdown_at_limit_is_rejected(
    manager,
):

    assert manager.check_drawdown(
        10_000,
        8_500,
    ) is False


def test_drawdown_above_limit_is_rejected(
    manager,
):

    assert manager.check_drawdown(
        10_000,
        8_000,
    ) is False


def test_invalid_peak_balance_returns_false(
    manager,
):

    assert manager.check_drawdown(
        0,
        9_000,
    ) is False


def test_kill_switch_activation(
    manager,
):

    manager.activate_kill_switch(
        "Emergency shutdown"
    )

    assert manager.kill_switch.active is True

    assert manager.kill_switch.reason == (
        "Emergency shutdown"
    )


def test_kill_switch_deactivation(
    manager,
):

    manager.activate_kill_switch()

    assert manager.kill_switch.active is True

    manager.deactivate_kill_switch()

    assert manager.kill_switch.active is False


def test_status_is_ok(manager):

    assert manager.status(
        daily_loss=0.01,
        peak_balance=10_000,
        current_balance=9_500,
    ) == RiskStatus.OK


def test_status_daily_loss_limit(manager):

    assert manager.status(
        daily_loss=0.05,
        peak_balance=10_000,
        current_balance=9_500,
    ) == RiskStatus.DAILY_LOSS_LIMIT


def test_status_max_drawdown(manager):

    assert manager.status(
        daily_loss=0.01,
        peak_balance=10_000,
        current_balance=8_500,
    ) == RiskStatus.MAX_DRAWDOWN


def test_status_kill_switch_has_priority(
    manager,
):

    manager.activate_kill_switch()

    assert manager.status(
        daily_loss=0.10,
        peak_balance=10_000,
        current_balance=8_000,
    ) == RiskStatus.KILL_SWITCH


def test_can_trade_matches_status(
    manager,
):

    assert manager.can_trade(
        daily_loss=0.01,
        peak_balance=10_000,
        current_balance=9_500,
    ) is True

    assert manager.can_trade(
        daily_loss=0.05,
        peak_balance=10_000,
        current_balance=9_500,
    ) is False


def test_custom_dependencies_are_preserved():

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

    assert manager.drawdown_guard is (
        drawdown_guard
    )

    assert manager.kill_switch is (
        kill_switch
    )


@pytest.mark.parametrize(
    "field",
    [
        "max_risk_per_trade",
        "max_daily_loss",
        "max_drawdown",
    ],
)
def test_zero_configuration_is_rejected(
    field,
):

    settings = RiskSettings(
        max_risk_per_trade=0.01,
        max_daily_loss=0.05,
        max_drawdown=0.15,
    )

    object.__setattr__(
        settings,
        field,
        0,
    )

    with pytest.raises(
        ValueError,
    ):

        RiskManager(
            settings=settings
        )


@pytest.mark.parametrize(
    "field",
    [
        "max_risk_per_trade",
        "max_daily_loss",
        "max_drawdown",
    ],
)
def test_invalid_configuration_is_rejected(
    field,
):

    settings = RiskSettings(
        max_risk_per_trade=0.01,
        max_daily_loss=0.05,
        max_drawdown=0.15,
    )

    object.__setattr__(
        settings,
        field,
        math.nan,
    )

    with pytest.raises(
        ValueError,
    ):

        RiskManager(
            settings=settings
        )


def test_risk_settings_are_immutable():

    settings = RiskSettings()

    with pytest.raises(
        AttributeError,
    ):

        settings.max_drawdown = 0.20


def test_risk_status_is_string_enum():

    assert RiskStatus.OK.value == "OK"

    assert (
        str(RiskStatus.OK.value)
        == "OK"
    )