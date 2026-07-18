import math

import pytest

from src.risk.pre_trade_validator import (
    PreTradeValidator,
    ValidationResult,
)


@pytest.fixture
def validator():

    return PreTradeValidator(
        max_position_size=100.0,
        max_leverage=10.0,
    )


def test_valid_trade_is_approved(validator):

    result = validator.validate(
        position_size=10.0,
        leverage=5.0,
        entry_price=100.0,
        stop_loss=95.0,
    )

    assert isinstance(
        result,
        ValidationResult,
    )

    assert result.approved is True

    assert result.reason is None


def test_position_size_zero_is_rejected(validator):

    result = validator.validate_position_size(0)

    assert result.approved is False

    assert result.reason == (
        "Position size must be a finite number greater than zero."
    )


def test_negative_position_size_is_rejected(validator):

    result = validator.validate_position_size(-1)

    assert result.approved is False


def test_position_size_above_limit_is_rejected(validator):

    result = validator.validate_position_size(100.01)

    assert result.approved is False

    assert result.reason == (
        "Position size exceeds maximum allowed."
    )


def test_valid_position_size_is_approved(validator):

    result = validator.validate_position_size(100)

    assert result.approved is True


def test_nan_position_size_is_rejected(validator):

    result = validator.validate_position_size(math.nan)

    assert result.approved is False


def test_infinite_position_size_is_rejected(validator):

    result = validator.validate_position_size(math.inf)

    assert result.approved is False


def test_zero_leverage_is_rejected(validator):

    result = validator.validate_leverage(0)

    assert result.approved is False


def test_negative_leverage_is_rejected(validator):

    result = validator.validate_leverage(-1)

    assert result.approved is False


def test_leverage_above_limit_is_rejected(validator):

    result = validator.validate_leverage(10.01)

    assert result.approved is False

    assert result.reason == (
        "Leverage exceeds maximum allowed."
    )


def test_valid_leverage_is_approved(validator):

    result = validator.validate_leverage(10)

    assert result.approved is True


def test_nan_leverage_is_rejected(validator):

    result = validator.validate_leverage(math.nan)

    assert result.approved is False


def test_infinite_leverage_is_rejected(validator):

    result = validator.validate_leverage(math.inf)

    assert result.approved is False


def test_invalid_entry_price_is_rejected(validator):

    result = validator.validate_stop_loss(
        entry_price=0,
        stop_loss=95,
    )

    assert result.approved is False


def test_invalid_stop_loss_is_rejected(validator):

    result = validator.validate_stop_loss(
        entry_price=100,
        stop_loss=0,
    )

    assert result.approved is False


def test_equal_entry_and_stop_loss_is_rejected(validator):

    result = validator.validate_stop_loss(
        entry_price=100,
        stop_loss=100,
    )

    assert result.approved is False

    assert result.reason == (
        "Stop loss cannot equal entry price."
    )


def test_valid_stop_loss_is_approved(validator):

    result = validator.validate_stop_loss(
        entry_price=100,
        stop_loss=95,
    )

    assert result.approved is True


def test_nan_entry_price_is_rejected(validator):

    result = validator.validate_stop_loss(
        entry_price=math.nan,
        stop_loss=95,
    )

    assert result.approved is False


def test_infinite_stop_loss_is_rejected(validator):

    result = validator.validate_stop_loss(
        entry_price=100,
        stop_loss=math.inf,
    )

    assert result.approved is False


@pytest.mark.parametrize(
    "max_position_size",
    [0, -1, math.nan, math.inf],
)
def test_invalid_max_position_size(max_position_size):

    with pytest.raises(
        (ValueError, TypeError)
    ):

        PreTradeValidator(
            max_position_size=max_position_size,
            max_leverage=10,
        )


@pytest.mark.parametrize(
    "max_leverage",
    [0, -1, math.nan, math.inf],
)
def test_invalid_max_leverage(max_leverage):

    with pytest.raises(
        (ValueError, TypeError)
    ):

        PreTradeValidator(
            max_position_size=100,
            max_leverage=max_leverage,
        )


def test_validation_stops_at_first_failure(validator):

    result = validator.validate(
        position_size=200,
        leverage=20,
        entry_price=100,
        stop_loss=100,
    )

    assert result.approved is False

    assert result.reason == (
        "Position size exceeds maximum allowed."
    )


def test_result_types(validator):

    result = validator.validate(
        position_size=10,
        leverage=5,
        entry_price=100,
        stop_loss=95,
    )

    assert isinstance(
        result.approved,
        bool,
    )

    assert result.reason is None