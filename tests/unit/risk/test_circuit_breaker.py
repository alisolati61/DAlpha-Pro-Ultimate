import math
from datetime import UTC, datetime, timedelta

import pytest

from src.risk.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerState,
)


def test_initial_state():

    breaker = CircuitBreaker()

    assert breaker.loss_counter == 0

    assert breaker.state.active is False

    assert breaker.state.reason == ""

    assert breaker.state.activated_at is None

    assert breaker.can_trade() is True


def test_loss_counter_increments():

    breaker = CircuitBreaker(
        max_consecutive_losses=3,
    )

    breaker.register_trade(-10)

    assert breaker.loss_counter == 1

    assert breaker.state.active is False


def test_consecutive_losses_activate_breaker():

    breaker = CircuitBreaker(
        max_consecutive_losses=3,
        cooldown_minutes=30,
    )

    breaker.register_trade(-10)

    breaker.register_trade(-20)

    breaker.register_trade(-30)

    assert breaker.loss_counter == 3

    assert breaker.state.active is True

    assert (
        breaker.state.reason
        == "Maximum consecutive losses reached."
    )

    assert isinstance(
        breaker.state.activated_at,
        datetime,
    )

    assert (
        breaker.state.activated_at.tzinfo
        == UTC
    )

    assert breaker.can_trade() is False


def test_profitable_trade_resets_loss_counter():

    breaker = CircuitBreaker(
        max_consecutive_losses=3,
    )

    breaker.register_trade(-10)

    breaker.register_trade(-20)

    assert breaker.loss_counter == 2

    breaker.register_trade(50)

    assert breaker.loss_counter == 0

    assert breaker.state.active is False


def test_zero_profit_resets_loss_counter():

    breaker = CircuitBreaker(
        max_consecutive_losses=3,
    )

    breaker.register_trade(-10)

    breaker.register_trade(-20)

    breaker.register_trade(0)

    assert breaker.loss_counter == 0

    assert breaker.state.active is False


def test_breaker_blocks_trading_during_cooldown():

    breaker = CircuitBreaker(
        max_consecutive_losses=1,
        cooldown_minutes=30,
    )

    breaker.register_trade(-1)

    assert breaker.state.active is True

    assert breaker.can_trade() is False


def test_breaker_deactivates_after_cooldown():

    breaker = CircuitBreaker(
        max_consecutive_losses=1,
        cooldown_minutes=30,
    )

    activated_at = (
        datetime.now(UTC)
        - timedelta(minutes=31)
    )

    breaker.state = CircuitBreakerState(
        active=True,
        reason="Test breaker",
        activated_at=activated_at,
    )

    assert breaker.can_trade() is True

    assert breaker.state.active is False

    assert breaker.state.reason == ""

    assert breaker.state.activated_at is None

    assert breaker.loss_counter == 0


def test_active_breaker_without_timestamp_blocks_trade():

    breaker = CircuitBreaker()

    breaker.state = CircuitBreakerState(
        active=True,
        reason="Manual stop",
        activated_at=None,
    )

    assert breaker.can_trade() is False


def test_manual_activation():

    breaker = CircuitBreaker()

    breaker.activate(
        "Manual risk shutdown"
    )

    assert breaker.state.active is True

    assert (
        breaker.state.reason
        == "Manual risk shutdown"
    )

    assert isinstance(
        breaker.state.activated_at,
        datetime,
    )


def test_manual_deactivation():

    breaker = CircuitBreaker(
        max_consecutive_losses=1,
    )

    breaker.register_trade(-1)

    assert breaker.state.active is True

    breaker.deactivate()

    assert breaker.state.active is False

    assert breaker.state.reason == ""

    assert breaker.state.activated_at is None

    assert breaker.loss_counter == 0

    assert breaker.can_trade() is True


@pytest.mark.parametrize(
    "profit",
    [
        math.nan,
        math.inf,
        -math.inf,
    ],
)
def test_invalid_profit_is_rejected(
    profit,
):

    breaker = CircuitBreaker()

    with pytest.raises(
        ValueError,
        match="Profit must be finite",
    ):

        breaker.register_trade(
            profit
        )


@pytest.mark.parametrize(
    "max_consecutive_losses",
    [
        0,
        -1,
    ],
)
def test_invalid_loss_threshold(
    max_consecutive_losses,
):

    with pytest.raises(
        ValueError,
    ):

        CircuitBreaker(
            max_consecutive_losses=(
                max_consecutive_losses
            ),
        )


def test_invalid_loss_threshold_type():

    with pytest.raises(
        TypeError,
    ):

        CircuitBreaker(
            max_consecutive_losses=2.5,
        )


def test_negative_cooldown_is_rejected():

    with pytest.raises(
        ValueError,
    ):

        CircuitBreaker(
            cooldown_minutes=-1,
        )


def test_invalid_cooldown_type():

    with pytest.raises(
        TypeError,
    ):

        CircuitBreaker(
            cooldown_minutes=2.5,
        )


def test_zero_cooldown_allows_trade_immediately():

    breaker = CircuitBreaker(
        max_consecutive_losses=1,
        cooldown_minutes=0,
    )

    breaker.register_trade(-1)

    assert breaker.state.active is True

    assert breaker.can_trade() is True

    assert breaker.state.active is False


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
    reason,
):

    breaker = CircuitBreaker()

    with pytest.raises(
        ValueError,
    ):

        breaker.activate(reason)


def test_activation_reason_is_stripped():

    breaker = CircuitBreaker()

    breaker.activate(
        "  Manual stop  "
    )

    assert (
        breaker.state.reason
        == "Manual stop"
    )


def test_invalid_activation_reason_type():

    breaker = CircuitBreaker()

    with pytest.raises(
        TypeError,
    ):

        breaker.activate(None)


def test_state_is_immutable():

    breaker = CircuitBreaker()

    with pytest.raises(
        AttributeError,
    ):

        breaker.state.active = True


def test_breaker_reactivates_with_new_timestamp():

    breaker = CircuitBreaker()

    breaker.activate(
        "First reason"
    )

    first_timestamp = (
        breaker.state.activated_at
    )

    breaker.activate(
        "Second reason"
    )

    second_timestamp = (
        breaker.state.activated_at
    )

    assert breaker.state.reason == (
        "Second reason"
    )

    assert second_timestamp is not None

    assert first_timestamp is not None

    assert second_timestamp >= (
        first_timestamp
    )


def test_result_types():

    breaker = CircuitBreaker()

    assert isinstance(
        breaker.state,
        CircuitBreakerState,
    )

    assert isinstance(
        breaker.state.active,
        bool,
    )

    assert isinstance(
        breaker.state.reason,
        str,
    )