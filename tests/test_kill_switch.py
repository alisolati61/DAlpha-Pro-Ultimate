"""Tests for the emergency trading kill switch."""

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta, timezone

import pytest

from src.risk.kill_switch import (
    KillSwitch,
    KillSwitchState,
)


def test_initial_state() -> None:
    kill_switch = KillSwitch()

    assert kill_switch.active is False
    assert kill_switch.is_active() is False
    assert kill_switch.reason == ""
    assert kill_switch.activated_at is None
    assert kill_switch.state == KillSwitchState()


def test_activate_with_default_reason() -> None:
    kill_switch = KillSwitch()

    kill_switch.activate()

    assert kill_switch.active is True
    assert kill_switch.is_active() is True
    assert kill_switch.reason == "Manual activation"
    assert isinstance(kill_switch.activated_at, datetime)
    assert kill_switch.activated_at is not None
    assert kill_switch.activated_at.tzinfo is UTC


def test_activate_with_custom_reason() -> None:
    kill_switch = KillSwitch()

    kill_switch.activate(
        "Emergency drawdown protection"
    )

    assert kill_switch.active is True
    assert (
        kill_switch.reason
        == "Emergency drawdown protection"
    )


def test_activation_reason_is_trimmed() -> None:
    kill_switch = KillSwitch()

    kill_switch.activate(
        "  Emergency stop  "
    )

    assert kill_switch.reason == "Emergency stop"


@pytest.mark.parametrize(
    "reason",
    [
        "",
        " ",
        "\t",
        "\n",
    ],
)
def test_empty_reason_is_rejected(
    reason: str,
) -> None:
    kill_switch = KillSwitch()

    with pytest.raises(
        ValueError,
        match="Reason cannot be empty",
    ):
        kill_switch.activate(reason)


@pytest.mark.parametrize(
    "reason",
    [
        None,
        1,
        True,
        object(),
    ],
)
def test_invalid_reason_type_is_rejected(
    reason: object,
) -> None:
    kill_switch = KillSwitch()

    with pytest.raises(
        TypeError,
        match="Reason must be a string",
    ):
        kill_switch.activate(
            reason,  # type: ignore[arg-type]
        )


def test_deactivate_resets_state() -> None:
    kill_switch = KillSwitch()
    kill_switch.activate(
        "Manual emergency stop"
    )

    kill_switch.deactivate()

    assert kill_switch.active is False
    assert kill_switch.is_active() is False
    assert kill_switch.reason == ""
    assert kill_switch.activated_at is None
    assert kill_switch.state == KillSwitchState()


def test_deactivate_is_idempotent() -> None:
    kill_switch = KillSwitch()

    kill_switch.deactivate()
    kill_switch.deactivate()

    assert kill_switch.state == KillSwitchState()


def test_reactivation_updates_reason_and_timestamp() -> None:
    timestamps = iter(
        (
            datetime(
                2026,
                7,
                24,
                10,
                0,
                tzinfo=UTC,
            ),
            datetime(
                2026,
                7,
                24,
                10,
                1,
                tzinfo=UTC,
            ),
        )
    )

    kill_switch = KillSwitch(
        clock=lambda: next(timestamps),
    )

    kill_switch.activate("First emergency")
    first_state = kill_switch.state

    kill_switch.activate("Second emergency")
    second_state = kill_switch.state

    assert first_state.active is True
    assert first_state.reason == "First emergency"

    assert second_state.active is True
    assert second_state.reason == "Second emergency"

    assert second_state.activated_at is not None
    assert first_state.activated_at is not None

    assert (
        second_state.activated_at
        > first_state.activated_at
    )


def test_previous_state_snapshot_is_not_mutated() -> None:
    activated_at = datetime(
        2026,
        7,
        24,
        10,
        0,
        tzinfo=UTC,
    )

    kill_switch = KillSwitch(
        clock=lambda: activated_at,
    )

    inactive_state = kill_switch.state
    kill_switch.activate("Emergency")
    active_state = kill_switch.state
    kill_switch.deactivate()

    assert inactive_state == KillSwitchState()

    assert active_state == KillSwitchState(
        active=True,
        reason="Emergency",
        activated_at=activated_at,
    )

    assert kill_switch.state == KillSwitchState()


def test_custom_clock_is_used() -> None:
    activated_at = datetime(
        2026,
        7,
        24,
        10,
        30,
        tzinfo=UTC,
    )

    kill_switch = KillSwitch(
        clock=lambda: activated_at,
    )

    kill_switch.activate()

    assert kill_switch.activated_at == activated_at


def test_non_utc_clock_value_is_normalized_to_utc() -> None:
    iran_timezone = timezone(
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
        tzinfo=iran_timezone,
    )

    kill_switch = KillSwitch(
        clock=lambda: local_time,
    )

    kill_switch.activate()

    assert kill_switch.activated_at == datetime(
        2026,
        7,
        24,
        10,
        30,
        tzinfo=UTC,
    )

    assert kill_switch.activated_at is not None
    assert kill_switch.activated_at.tzinfo is UTC


@pytest.mark.parametrize(
    "clock",
    [
        1,
        "clock",
        object(),
    ],
)
def test_rejects_non_callable_clock(
    clock: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="clock must be callable or None",
    ):
        KillSwitch(
            clock=clock,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "value",
    [
        None,
        "2026-07-24",
        1,
        object(),
    ],
)
def test_clock_must_return_datetime(
    value: object,
) -> None:
    kill_switch = KillSwitch(
        clock=lambda: value,  # type: ignore[return-value]
    )

    with pytest.raises(
        TypeError,
        match="clock result must be a datetime",
    ):
        kill_switch.activate()


def test_clock_must_return_timezone_aware_datetime() -> None:
    kill_switch = KillSwitch(
        clock=lambda: datetime(
            2026,
            7,
            24,
            10,
            30,
        )
    )

    with pytest.raises(
        ValueError,
        match=(
            "clock result must be "
            "timezone-aware"
        ),
    ):
        kill_switch.activate()


def test_failed_activation_preserves_previous_state() -> None:
    kill_switch = KillSwitch(
        clock=lambda: datetime(
            2026,
            7,
            24,
            10,
            30,
        )
    )

    previous_state = kill_switch.state

    with pytest.raises(ValueError):
        kill_switch.activate("Emergency")

    assert kill_switch.state is previous_state
    assert kill_switch.active is False


def test_state_is_immutable() -> None:
    state = KillSwitchState()

    with pytest.raises(FrozenInstanceError):
        state.active = True  # type: ignore[misc]


def test_active_state_is_immutable() -> None:
    state = KillSwitchState(
        active=True,
        reason="Emergency",
        activated_at=datetime.now(UTC),
    )

    with pytest.raises(FrozenInstanceError):
        state.reason = "Changed"  # type: ignore[misc]


@pytest.mark.parametrize(
    "active",
    [
        1,
        "False",
        None,
    ],
)
def test_state_rejects_non_boolean_active(
    active: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="active must be a bool",
    ):
        KillSwitchState(
            active=active,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "reason",
    [
        None,
        1,
        True,
        object(),
    ],
)
def test_state_rejects_non_string_reason(
    reason: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="reason must be a string",
    ):
        KillSwitchState(
            reason=reason,  # type: ignore[arg-type]
        )


def test_active_state_requires_reason() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "reason must not be empty "
            "when active"
        ),
    ):
        KillSwitchState(
            active=True,
            activated_at=datetime.now(UTC),
        )


def test_active_state_requires_activation_time() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "activated_at is required "
            "when active"
        ),
    ):
        KillSwitchState(
            active=True,
            reason="Emergency",
        )


def test_inactive_state_rejects_reason() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "reason must be empty "
            "when inactive"
        ),
    ):
        KillSwitchState(
            reason="Emergency",
        )


def test_inactive_state_rejects_activation_time() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "activated_at must be None "
            "when inactive"
        ),
    ):
        KillSwitchState(
            activated_at=datetime.now(UTC),
        )


@pytest.mark.parametrize(
    "value",
    [
        1,
        "2026-07-24",
        object(),
    ],
)
def test_active_state_rejects_non_datetime_activation_time(
    value: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="activated_at must be a datetime",
    ):
        KillSwitchState(
            active=True,
            reason="Emergency",
            activated_at=value,  # type: ignore[arg-type]
        )


def test_active_state_rejects_naive_activation_time() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "activated_at must be "
            "timezone-aware"
        ),
    ):
        KillSwitchState(
            active=True,
            reason="Emergency",
            activated_at=datetime(
                2026,
                7,
                24,
                10,
                0,
            ),
        )


def test_active_state_normalizes_reason_and_timezone() -> None:
    offset = timezone(
        timedelta(
            hours=-4,
        )
    )

    state = KillSwitchState(
        active=True,
        reason="  Emergency  ",
        activated_at=datetime(
            2026,
            7,
            24,
            8,
            0,
            tzinfo=offset,
        ),
    )

    assert state.reason == "Emergency"

    assert state.activated_at == datetime(
        2026,
        7,
        24,
        12,
        0,
        tzinfo=UTC,
    )

    assert state.activated_at.tzinfo is UTC


def test_result_property_types() -> None:
    kill_switch = KillSwitch()

    assert isinstance(kill_switch.active, bool)
    assert isinstance(kill_switch.reason, str)
    assert kill_switch.activated_at is None

    kill_switch.activate()

    assert isinstance(kill_switch.active, bool)
    assert isinstance(kill_switch.reason, str)
    assert isinstance(kill_switch.activated_at, datetime)