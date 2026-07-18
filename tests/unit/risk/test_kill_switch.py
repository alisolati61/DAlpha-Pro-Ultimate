from datetime import UTC, datetime

import pytest

from src.risk.kill_switch import (
    KillSwitch,
    KillSwitchState,
)


def test_initial_state():

    kill_switch = KillSwitch()

    assert kill_switch.active is False

    assert kill_switch.reason == ""

    assert kill_switch.activated_at is None

    assert kill_switch.state == (
        KillSwitchState()
    )


def test_activate_with_default_reason():

    kill_switch = KillSwitch()

    kill_switch.activate()

    assert kill_switch.active is True

    assert kill_switch.reason == (
        "Manual activation"
    )

    assert isinstance(
        kill_switch.activated_at,
        datetime,
    )

    assert (
        kill_switch.activated_at.tzinfo
        == UTC
    )


def test_activate_with_custom_reason():

    kill_switch = KillSwitch()

    kill_switch.activate(
        "Emergency drawdown protection"
    )

    assert kill_switch.active is True

    assert kill_switch.reason == (
        "Emergency drawdown protection"
    )


def test_activation_reason_is_trimmed():

    kill_switch = KillSwitch()

    kill_switch.activate(
        "  Emergency stop  "
    )

    assert kill_switch.reason == (
        "Emergency stop"
    )


@pytest.mark.parametrize(
    "reason",
    [
        "",
        " ",
        "\t",
        "\n",
    ],
)
def test_empty_reason_is_rejected(reason):

    kill_switch = KillSwitch()

    with pytest.raises(
        ValueError,
        match="Reason cannot be empty",
    ):

        kill_switch.activate(reason)


def test_invalid_reason_type_is_rejected():

    kill_switch = KillSwitch()

    with pytest.raises(
        TypeError,
        match="Reason must be a string",
    ):

        kill_switch.activate(None)


def test_deactivate_resets_state():

    kill_switch = KillSwitch()

    kill_switch.activate(
        "Manual emergency stop"
    )

    assert kill_switch.active is True

    kill_switch.deactivate()

    assert kill_switch.active is False

    assert kill_switch.reason == ""

    assert kill_switch.activated_at is None

    assert kill_switch.state == (
        KillSwitchState()
    )


def test_deactivate_is_idempotent():

    kill_switch = KillSwitch()

    kill_switch.deactivate()

    kill_switch.deactivate()

    assert kill_switch.active is False

    assert kill_switch.reason == ""

    assert kill_switch.activated_at is None


def test_reactivation_updates_reason():

    kill_switch = KillSwitch()

    kill_switch.activate(
        "First emergency"
    )

    first_timestamp = (
        kill_switch.activated_at
    )

    kill_switch.activate(
        "Second emergency"
    )

    second_timestamp = (
        kill_switch.activated_at
    )

    assert kill_switch.active is True

    assert kill_switch.reason == (
        "Second emergency"
    )

    assert first_timestamp is not None

    assert second_timestamp is not None

    assert second_timestamp >= (
        first_timestamp
    )


def test_state_is_immutable():

    kill_switch = KillSwitch()

    kill_switch.activate(
        "Emergency stop"
    )

    with pytest.raises(
        AttributeError,
    ):

        kill_switch.state.active = False


def test_state_property_reflects_activation():

    kill_switch = KillSwitch()

    assert kill_switch.state.active is False

    kill_switch.activate(
        "Risk limit exceeded"
    )

    assert kill_switch.state.active is True

    assert kill_switch.state.reason == (
        "Risk limit exceeded"
    )


def test_result_types():

    kill_switch = KillSwitch()

    assert isinstance(
        kill_switch.active,
        bool,
    )

    assert isinstance(
        kill_switch.reason,
        str,
    )

    assert (
        kill_switch.activated_at is None
    )

    kill_switch.activate()

    assert isinstance(
        kill_switch.active,
        bool,
    )

    assert isinstance(
        kill_switch.reason,
        str,
    )

    assert isinstance(
        kill_switch.activated_at,
        datetime,
    )