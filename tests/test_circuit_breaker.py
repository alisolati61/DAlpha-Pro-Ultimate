"""Tests for the consecutive-loss circuit breaker."""

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta, timezone
from math import inf, nan

import pytest

from src.risk.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerState,
)


def test_initial_state_and_configuration() -> None:
    breaker = CircuitBreaker()

    assert breaker.max_consecutive_losses == 5
    assert breaker.cooldown == timedelta(minutes=30)
    assert breaker.cooldown_minutes == 30
    assert breaker.loss_counter == 0

    assert breaker.state == CircuitBreakerState()
    assert breaker.active is False
    assert breaker.reason == ""
    assert breaker.activated_at is None
    assert breaker.can_trade() is True
    assert breaker.cooldown_remaining() is None


def test_loss_counter_increments() -> None:
    breaker = CircuitBreaker(
        max_consecutive_losses=3,
    )

    breaker.register_trade(-10)

    assert breaker.loss_counter == 1
    assert breaker.active is False


def test_consecutive_losses_activate_breaker() -> None:
    activated_at = datetime(
        2026,
        7,
        24,
        10,
        0,
        tzinfo=UTC,
    )

    breaker = CircuitBreaker(
        max_consecutive_losses=3,
        cooldown_minutes=30,
        clock=lambda: activated_at,
    )

    breaker.register_trade(-10)
    breaker.register_trade(-20)
    breaker.register_trade(-30)

    assert breaker.loss_counter == 3
    assert breaker.active is True

    assert (
        breaker.reason
        == "Maximum consecutive losses reached."
    )

    assert breaker.activated_at == activated_at
    assert breaker.can_trade() is False


@pytest.mark.parametrize(
    "profit",
    [
        0,
        10,
        1.5,
    ],
)
def test_non_losing_trade_resets_loss_counter(
    profit: float,
) -> None:
    breaker = CircuitBreaker(
        max_consecutive_losses=3,
    )

    breaker.register_trade(-10)
    breaker.register_trade(-20)
    breaker.register_trade(profit)

    assert breaker.loss_counter == 0
    assert breaker.active is False


def test_loss_counter_requires_consecutive_losses() -> None:
    breaker = CircuitBreaker(
        max_consecutive_losses=3,
    )

    breaker.register_trade(-1)
    breaker.register_trade(-1)
    breaker.register_trade(0)
    breaker.register_trade(-1)
    breaker.register_trade(-1)

    assert breaker.loss_counter == 2
    assert breaker.active is False


def test_breaker_blocks_during_cooldown() -> None:
    now = datetime(
        2026,
        7,
        24,
        10,
        0,
        tzinfo=UTC,
    )

    breaker = CircuitBreaker(
        max_consecutive_losses=1,
        cooldown_minutes=30,
        clock=lambda: now,
    )

    breaker.register_trade(-1)

    assert breaker.can_trade() is False
    assert breaker.active is True


def test_breaker_remains_active_before_exact_boundary() -> None:
    activated_at = datetime(
        2026,
        7,
        24,
        10,
        0,
        tzinfo=UTC,
    )

    now = activated_at + timedelta(
        minutes=29,
        seconds=59,
        microseconds=999999,
    )

    breaker = CircuitBreaker(
        cooldown_minutes=30,
        clock=lambda: now,
    )

    breaker.state = CircuitBreakerState(
        active=True,
        reason="Testing",
        activated_at=activated_at,
    )

    assert breaker.can_trade() is False
    assert breaker.active is True


def test_breaker_deactivates_at_exact_cooldown_boundary() -> None:
    activated_at = datetime(
        2026,
        7,
        24,
        10,
        0,
        tzinfo=UTC,
    )

    now = activated_at + timedelta(
        minutes=30,
    )

    breaker = CircuitBreaker(
        cooldown_minutes=30,
        clock=lambda: now,
    )
    breaker.loss_counter = 4
    breaker.state = CircuitBreakerState(
        active=True,
        reason="Testing",
        activated_at=activated_at,
    )

    assert breaker.can_trade() is True

    assert breaker.state == CircuitBreakerState()
    assert breaker.loss_counter == 0


def test_breaker_deactivates_after_cooldown() -> None:
    activated_at = datetime(
        2026,
        7,
        24,
        10,
        0,
        tzinfo=UTC,
    )

    now = activated_at + timedelta(
        minutes=31,
    )

    breaker = CircuitBreaker(
        cooldown_minutes=30,
        clock=lambda: now,
    )
    breaker.loss_counter = 3
    breaker.state = CircuitBreakerState(
        active=True,
        reason="Testing",
        activated_at=activated_at,
    )

    assert breaker.can_trade() is True
    assert breaker.active is False
    assert breaker.loss_counter == 0


def test_zero_cooldown_allows_trade_immediately() -> None:
    now = datetime(
        2026,
        7,
        24,
        10,
        0,
        tzinfo=UTC,
    )

    breaker = CircuitBreaker(
        max_consecutive_losses=1,
        cooldown_minutes=0,
        clock=lambda: now,
    )

    breaker.register_trade(-1)

    assert breaker.active is True
    assert breaker.can_trade() is True
    assert breaker.active is False


def test_active_breaker_without_timestamp_fails_closed() -> None:
    breaker = CircuitBreaker()

    breaker.state = CircuitBreakerState(
        active=True,
        reason="Manual stop",
        activated_at=None,
    )

    assert breaker.can_trade() is False
    assert breaker.active is True
    assert breaker.cooldown_remaining() == timedelta(
        minutes=30,
    )


def test_manual_activation() -> None:
    activated_at = datetime(
        2026,
        7,
        24,
        10,
        0,
        tzinfo=UTC,
    )

    breaker = CircuitBreaker(
        clock=lambda: activated_at,
    )

    breaker.activate(
        "Manual risk shutdown"
    )

    assert breaker.active is True
    assert breaker.reason == "Manual risk shutdown"
    assert breaker.activated_at == activated_at


def test_activation_reason_is_stripped() -> None:
    breaker = CircuitBreaker()

    breaker.activate(
        "  Manual stop  "
    )

    assert breaker.reason == "Manual stop"


def test_manual_deactivation() -> None:
    breaker = CircuitBreaker(
        max_consecutive_losses=1,
    )

    breaker.register_trade(-1)
    breaker.deactivate()

    assert breaker.state == CircuitBreakerState()
    assert breaker.loss_counter == 0
    assert breaker.can_trade() is True


def test_deactivation_is_idempotent() -> None:
    breaker = CircuitBreaker()

    breaker.deactivate()
    breaker.deactivate()

    assert breaker.state == CircuitBreakerState()
    assert breaker.loss_counter == 0


def test_reactivation_replaces_state_snapshot() -> None:
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

    breaker = CircuitBreaker(
        clock=lambda: next(timestamps),
    )

    breaker.activate("First reason")
    first_state = breaker.state

    breaker.activate("Second reason")
    second_state = breaker.state

    assert first_state.reason == "First reason"

    assert first_state.activated_at == datetime(
        2026,
        7,
        24,
        10,
        0,
        tzinfo=UTC,
    )

    assert second_state.reason == "Second reason"

    assert second_state.activated_at == datetime(
        2026,
        7,
        24,
        10,
        1,
        tzinfo=UTC,
    )


def test_failed_reactivation_preserves_previous_state() -> None:
    good_time = datetime(
        2026,
        7,
        24,
        10,
        0,
        tzinfo=UTC,
    )

    values = iter(
        (
            good_time,
            datetime(
                2026,
                7,
                24,
                10,
                1,
            ),
        )
    )

    breaker = CircuitBreaker(
        clock=lambda: next(values),
    )
    breaker.activate("Valid activation")
    previous_state = breaker.state

    with pytest.raises(
        ValueError,
        match="clock result must be timezone-aware",
    ):
        breaker.activate("Invalid activation")

    assert breaker.state is previous_state


def test_cooldown_remaining() -> None:
    activated_at = datetime(
        2026,
        7,
        24,
        10,
        0,
        tzinfo=UTC,
    )

    now = activated_at + timedelta(
        minutes=12,
        seconds=30,
    )

    breaker = CircuitBreaker(
        cooldown_minutes=30,
        clock=lambda: now,
    )
    breaker.state = CircuitBreakerState(
        active=True,
        reason="Testing",
        activated_at=activated_at,
    )

    assert breaker.cooldown_remaining() == timedelta(
        minutes=17,
        seconds=30,
    )


def test_expired_cooldown_remaining_is_zero_without_mutation() -> None:
    activated_at = datetime(
        2026,
        7,
        24,
        10,
        0,
        tzinfo=UTC,
    )

    breaker = CircuitBreaker(
        cooldown_minutes=30,
        clock=lambda: (
            activated_at
            + timedelta(minutes=31)
        ),
    )
    breaker.state = CircuitBreakerState(
        active=True,
        reason="Testing",
        activated_at=activated_at,
    )

    assert breaker.cooldown_remaining() == timedelta(0)
    assert breaker.active is True


@pytest.mark.parametrize(
    "profit",
    [
        True,
        False,
        "1",
        None,
        object(),
    ],
)
def test_non_numeric_profit_is_rejected(
    profit: object,
) -> None:
    breaker = CircuitBreaker()

    with pytest.raises(
        TypeError,
        match="Profit must be a number",
    ):
        breaker.register_trade(
            profit,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "profit",
    [
        nan,
        inf,
        -inf,
    ],
)
def test_non_finite_profit_is_rejected(
    profit: float,
) -> None:
    breaker = CircuitBreaker()

    with pytest.raises(
        ValueError,
        match="Profit must be finite",
    ):
        breaker.register_trade(profit)


@pytest.mark.parametrize(
    "value",
    [
        0,
        -1,
    ],
)
def test_invalid_loss_threshold(
    value: int,
) -> None:
    with pytest.raises(
        ValueError,
        match=(
            "max_consecutive_losses must be "
            "greater than zero"
        ),
    ):
        CircuitBreaker(
            max_consecutive_losses=value,
        )


@pytest.mark.parametrize(
    "value",
    [
        True,
        False,
        2.5,
        "2",
        None,
    ],
)
def test_invalid_loss_threshold_type(
    value: object,
) -> None:
    with pytest.raises(
        TypeError,
        match=(
            "max_consecutive_losses must be "
            "an integer"
        ),
    ):
        CircuitBreaker(
            max_consecutive_losses=value,  # type: ignore[arg-type]
        )


def test_negative_cooldown_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="cooldown_minutes cannot be negative",
    ):
        CircuitBreaker(
            cooldown_minutes=-1,
        )


@pytest.mark.parametrize(
    "value",
    [
        True,
        False,
        2.5,
        "30",
        None,
    ],
)
def test_invalid_cooldown_type(
    value: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="cooldown_minutes must be an integer",
    ):
        CircuitBreaker(
            cooldown_minutes=value,  # type: ignore[arg-type]
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
def test_empty_activation_reason_is_rejected(
    reason: str,
) -> None:
    breaker = CircuitBreaker()

    with pytest.raises(
        ValueError,
        match="Reason cannot be empty",
    ):
        breaker.activate(reason)


@pytest.mark.parametrize(
    "reason",
    [
        None,
        1,
        True,
        object(),
    ],
)
def test_invalid_activation_reason_type(
    reason: object,
) -> None:
    breaker = CircuitBreaker()

    with pytest.raises(
        TypeError,
        match="Reason must be a string",
    ):
        breaker.activate(
            reason,  # type: ignore[arg-type]
        )


def test_activation_reason_length_is_bounded() -> None:
    breaker = CircuitBreaker()

    with pytest.raises(
        ValueError,
        match="Reason must not exceed 500 characters",
    ):
        breaker.activate(
            "x" * 501
        )


@pytest.mark.parametrize(
    "clock",
    [
        1,
        "clock",
        object(),
    ],
)
def test_invalid_clock_is_rejected(
    clock: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="clock must be callable or None",
    ):
        CircuitBreaker(
            clock=clock,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "value",
    [
        None,
        1,
        "2026-07-24",
        object(),
    ],
)
def test_clock_must_return_datetime(
    value: object,
) -> None:
    breaker = CircuitBreaker(
        clock=lambda: value,  # type: ignore[return-value]
    )

    with pytest.raises(
        TypeError,
        match="clock result must be a datetime",
    ):
        breaker.activate("Testing")


def test_clock_must_return_timezone_aware_datetime() -> None:
    breaker = CircuitBreaker(
        clock=lambda: datetime(
            2026,
            7,
            24,
            10,
            0,
        )
    )

    with pytest.raises(
        ValueError,
        match="clock result must be timezone-aware",
    ):
        breaker.activate("Testing")


def test_non_utc_clock_value_is_normalized() -> None:
    local_timezone = timezone(
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
        tzinfo=local_timezone,
    )

    breaker = CircuitBreaker(
        clock=lambda: local_time,
    )
    breaker.activate("Testing")

    assert breaker.activated_at == datetime(
        2026,
        7,
        24,
        10,
        30,
        tzinfo=UTC,
    )

    assert breaker.activated_at is not None
    assert breaker.activated_at.tzinfo is UTC


def test_state_is_immutable() -> None:
    state = CircuitBreakerState()

    with pytest.raises(
        FrozenInstanceError,
    ):
        state.active = True  # type: ignore[misc]


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
        CircuitBreakerState(
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
        CircuitBreakerState(
            reason=reason,  # type: ignore[arg-type]
        )


def test_active_state_requires_reason() -> None:
    with pytest.raises(
        ValueError,
        match="reason must not be empty when active",
    ):
        CircuitBreakerState(
            active=True,
        )


def test_inactive_state_rejects_reason() -> None:
    with pytest.raises(
        ValueError,
        match="reason must be empty when inactive",
    ):
        CircuitBreakerState(
            reason="Testing",
        )


def test_inactive_state_rejects_timestamp() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "activated_at must be None "
            "when inactive"
        ),
    ):
        CircuitBreakerState(
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
def test_state_rejects_invalid_timestamp_type(
    value: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="activated_at must be a datetime",
    ):
        CircuitBreakerState(
            active=True,
            reason="Testing",
            activated_at=value,  # type: ignore[arg-type]
        )


def test_state_rejects_naive_timestamp() -> None:
    with pytest.raises(
        ValueError,
        match="activated_at must be timezone-aware",
    ):
        CircuitBreakerState(
            active=True,
            reason="Testing",
            activated_at=datetime(
                2026,
                7,
                24,
                10,
                0,
            ),
        )


def test_state_normalizes_reason_and_timestamp() -> None:
    offset = timezone(
        timedelta(
            hours=-4,
        )
    )

    state = CircuitBreakerState(
        active=True,
        reason="  Testing  ",
        activated_at=datetime(
            2026,
            7,
            24,
            8,
            0,
            tzinfo=offset,
        ),
    )

    assert state.reason == "Testing"

    assert state.activated_at == datetime(
        2026,
        7,
        24,
        12,
        0,
        tzinfo=UTC,
    )

    assert state.activated_at.tzinfo is UTC


def test_state_reason_length_is_bounded() -> None:
    with pytest.raises(
        ValueError,
        match="reason must not exceed 500 characters",
    ):
        CircuitBreakerState(
            active=True,
            reason="x" * 501,
        )


def test_result_property_types() -> None:
    breaker = CircuitBreaker()

    assert isinstance(
        breaker.state,
        CircuitBreakerState,
    )
    assert isinstance(
        breaker.active,
        bool,
    )
    assert isinstance(
        breaker.reason,
        str,
    )
    assert breaker.activated_at is None
    assert isinstance(
        breaker.cooldown_minutes,
        int,
    )