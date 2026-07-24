"""Tests for deterministic generic pre-trade validation."""

from dataclasses import FrozenInstanceError
from fractions import Fraction
from math import inf, nan

import pytest

from src.risk.pre_trade_validator import (
    PreTradeValidator,
    ValidationResult,
)


@pytest.fixture
def validator() -> PreTradeValidator:
    return PreTradeValidator(
        max_position_size=100.0,
        max_leverage=10.0,
    )


def test_configuration_is_normalized_to_float() -> None:
    validator = PreTradeValidator(
        max_position_size=100,
        max_leverage=10,
    )

    assert validator.max_position_size == 100.0
    assert validator.max_leverage == 10.0
    assert type(validator.max_position_size) is float
    assert type(validator.max_leverage) is float


def test_fraction_configuration_is_supported() -> None:
    validator = PreTradeValidator(
        max_position_size=Fraction(100, 1),
        max_leverage=Fraction(10, 1),
    )

    assert validator.max_position_size == 100.0
    assert validator.max_leverage == 10.0


def test_valid_trade_is_approved(
    validator: PreTradeValidator,
) -> None:
    result = validator.validate(
        position_size=10.0,
        leverage=5.0,
        entry_price=100.0,
        stop_loss=95.0,
    )

    assert result == ValidationResult.approve()
    assert result.approved is True
    assert result.rejected is False
    assert result.reason is None


def test_stop_above_entry_is_generically_valid(
    validator: PreTradeValidator,
) -> None:
    result = validator.validate(
        position_size=10.0,
        leverage=5.0,
        entry_price=100.0,
        stop_loss=105.0,
    )

    assert result.approved is True


def test_position_size_at_limit_is_approved(
    validator: PreTradeValidator,
) -> None:
    result = validator.validate_position_size(
        100.0
    )

    assert result.approved is True


def test_position_size_above_limit_is_rejected(
    validator: PreTradeValidator,
) -> None:
    result = validator.validate_position_size(
        100.000001
    )

    assert result == ValidationResult.reject(
        "Position size exceeds maximum allowed."
    )


@pytest.mark.parametrize(
    "position_size",
    [
        0,
        -1,
        nan,
        inf,
        -inf,
        True,
        False,
        "10",
        None,
        object(),
    ],
)
def test_invalid_position_size_is_rejected(
    validator: PreTradeValidator,
    position_size: object,
) -> None:
    result = validator.validate_position_size(
        position_size,  # type: ignore[arg-type]
    )

    assert result == ValidationResult.reject(
        "Position size must be a finite number "
        "greater than zero."
    )


def test_fraction_position_size_is_supported(
    validator: PreTradeValidator,
) -> None:
    result = validator.validate_position_size(
        Fraction(100, 1)
    )

    assert result.approved is True


def test_leverage_at_limit_is_approved(
    validator: PreTradeValidator,
) -> None:
    result = validator.validate_leverage(
        10.0
    )

    assert result.approved is True


def test_leverage_above_limit_is_rejected(
    validator: PreTradeValidator,
) -> None:
    result = validator.validate_leverage(
        10.000001
    )

    assert result == ValidationResult.reject(
        "Leverage exceeds maximum allowed."
    )


@pytest.mark.parametrize(
    "leverage",
    [
        0,
        -1,
        nan,
        inf,
        -inf,
        True,
        False,
        "5",
        None,
        object(),
    ],
)
def test_invalid_leverage_is_rejected(
    validator: PreTradeValidator,
    leverage: object,
) -> None:
    result = validator.validate_leverage(
        leverage,  # type: ignore[arg-type]
    )

    assert result == ValidationResult.reject(
        "Leverage must be a finite number "
        "greater than zero."
    )


def test_fraction_leverage_is_supported(
    validator: PreTradeValidator,
) -> None:
    result = validator.validate_leverage(
        Fraction(5, 1)
    )

    assert result.approved is True


def test_valid_entry_price_is_approved(
    validator: PreTradeValidator,
) -> None:
    assert validator.validate_entry_price(
        100
    ).approved is True


@pytest.mark.parametrize(
    "entry_price",
    [
        0,
        -1,
        nan,
        inf,
        -inf,
        True,
        False,
        "100",
        None,
        object(),
    ],
)
def test_invalid_entry_price_is_rejected(
    validator: PreTradeValidator,
    entry_price: object,
) -> None:
    result = validator.validate_entry_price(
        entry_price,  # type: ignore[arg-type]
    )

    assert result == ValidationResult.reject(
        "Entry price must be a finite number "
        "greater than zero."
    )


def test_valid_stop_loss_price_is_approved(
    validator: PreTradeValidator,
) -> None:
    assert validator.validate_stop_loss_price(
        95
    ).approved is True


@pytest.mark.parametrize(
    "stop_loss",
    [
        0,
        -1,
        nan,
        inf,
        -inf,
        True,
        False,
        "95",
        None,
        object(),
    ],
)
def test_invalid_stop_loss_price_is_rejected(
    validator: PreTradeValidator,
    stop_loss: object,
) -> None:
    result = validator.validate_stop_loss_price(
        stop_loss,  # type: ignore[arg-type]
    )

    assert result == ValidationResult.reject(
        "Stop loss must be a finite number "
        "greater than zero."
    )


def test_equal_entry_and_stop_is_rejected(
    validator: PreTradeValidator,
) -> None:
    result = validator.validate_stop_loss(
        entry_price=100,
        stop_loss=100,
    )

    assert result == ValidationResult.reject(
        "Stop loss cannot equal entry price."
    )


def test_stop_loss_validation_checks_entry_first(
    validator: PreTradeValidator,
) -> None:
    result = validator.validate_stop_loss(
        entry_price=0,
        stop_loss=0,
    )

    assert result.reason == (
        "Entry price must be a finite number "
        "greater than zero."
    )


def test_stop_loss_validation_checks_stop_second(
    validator: PreTradeValidator,
) -> None:
    result = validator.validate_stop_loss(
        entry_price=100,
        stop_loss=0,
    )

    assert result.reason == (
        "Stop loss must be a finite number "
        "greater than zero."
    )


def test_valid_stop_loss_pair_is_approved(
    validator: PreTradeValidator,
) -> None:
    result = validator.validate_stop_loss(
        entry_price=100,
        stop_loss=95,
    )

    assert result.approved is True


def test_validate_stops_at_position_size_failure(
    validator: PreTradeValidator,
) -> None:
    result = validator.validate(
        position_size=200,
        leverage=20,
        entry_price=100,
        stop_loss=100,
    )

    assert result.reason == (
        "Position size exceeds maximum allowed."
    )


def test_validate_stops_at_leverage_failure(
    validator: PreTradeValidator,
) -> None:
    result = validator.validate(
        position_size=10,
        leverage=20,
        entry_price=100,
        stop_loss=100,
    )

    assert result.reason == (
        "Leverage exceeds maximum allowed."
    )


def test_validate_reaches_stop_loss_failure(
    validator: PreTradeValidator,
) -> None:
    result = validator.validate(
        position_size=10,
        leverage=5,
        entry_price=100,
        stop_loss=100,
    )

    assert result.reason == (
        "Stop loss cannot equal entry price."
    )


def test_validate_all_returns_every_failure(
    validator: PreTradeValidator,
) -> None:
    results = validator.validate_all(
        position_size=200,
        leverage=20,
        entry_price=100,
        stop_loss=100,
    )

    assert results == (
        ValidationResult.reject(
            "Position size exceeds maximum allowed."
        ),
        ValidationResult.reject(
            "Leverage exceeds maximum allowed."
        ),
        ValidationResult.reject(
            "Stop loss cannot equal entry price."
        ),
    )


def test_validate_all_returns_single_approval(
    validator: PreTradeValidator,
) -> None:
    results = validator.validate_all(
        position_size=10,
        leverage=5,
        entry_price=100,
        stop_loss=95,
    )

    assert results == (
        ValidationResult.approve(),
    )


def test_validate_all_result_is_tuple(
    validator: PreTradeValidator,
) -> None:
    result = validator.validate_all(
        position_size=10,
        leverage=5,
        entry_price=100,
        stop_loss=95,
    )

    assert type(result) is tuple


def test_position_size_utilization(
    validator: PreTradeValidator,
) -> None:
    assert validator.position_size_utilization(
        25
    ) == 0.25


def test_position_size_utilization_can_exceed_one(
    validator: PreTradeValidator,
) -> None:
    assert validator.position_size_utilization(
        125
    ) == 1.25


def test_leverage_utilization(
    validator: PreTradeValidator,
) -> None:
    assert validator.leverage_utilization(
        5
    ) == 0.5


@pytest.mark.parametrize(
    "value",
    [
        0,
        -1,
    ],
)
def test_utilization_rejects_non_positive_value(
    validator: PreTradeValidator,
    value: float,
) -> None:
    with pytest.raises(
        ValueError,
        match="greater than zero",
    ):
        validator.position_size_utilization(
            value
        )


@pytest.mark.parametrize(
    "value",
    [
        nan,
        inf,
        -inf,
    ],
)
def test_utilization_rejects_non_finite_value(
    validator: PreTradeValidator,
    value: float,
) -> None:
    with pytest.raises(
        ValueError,
        match="must be finite",
    ):
        validator.leverage_utilization(
            value
        )


@pytest.mark.parametrize(
    "value",
    [
        True,
        False,
        "1",
        None,
        object(),
    ],
)
def test_utilization_rejects_non_numeric_value(
    validator: PreTradeValidator,
    value: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="must be a number",
    ):
        validator.position_size_utilization(
            value  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "max_position_size",
    [
        0,
        -1,
    ],
)
def test_invalid_max_position_size_value(
    max_position_size: float,
) -> None:
    with pytest.raises(
        ValueError,
        match=(
            "max_position_size must be "
            "greater than zero"
        ),
    ):
        PreTradeValidator(
            max_position_size=max_position_size,
            max_leverage=10,
        )


@pytest.mark.parametrize(
    "max_position_size",
    [
        nan,
        inf,
        -inf,
    ],
)
def test_non_finite_max_position_size(
    max_position_size: float,
) -> None:
    with pytest.raises(
        ValueError,
        match=(
            "max_position_size must be finite"
        ),
    ):
        PreTradeValidator(
            max_position_size=max_position_size,
            max_leverage=10,
        )


@pytest.mark.parametrize(
    "max_position_size",
    [
        True,
        False,
        "100",
        None,
        object(),
    ],
)
def test_non_numeric_max_position_size(
    max_position_size: object,
) -> None:
    with pytest.raises(
        TypeError,
        match=(
            "max_position_size must be a number"
        ),
    ):
        PreTradeValidator(
            max_position_size=max_position_size,  # type: ignore[arg-type]
            max_leverage=10,
        )


@pytest.mark.parametrize(
    "max_leverage",
    [
        0,
        -1,
    ],
)
def test_invalid_max_leverage_value(
    max_leverage: float,
) -> None:
    with pytest.raises(
        ValueError,
        match=(
            "max_leverage must be "
            "greater than zero"
        ),
    ):
        PreTradeValidator(
            max_position_size=100,
            max_leverage=max_leverage,
        )


@pytest.mark.parametrize(
    "max_leverage",
    [
        nan,
        inf,
        -inf,
    ],
)
def test_non_finite_max_leverage(
    max_leverage: float,
) -> None:
    with pytest.raises(
        ValueError,
        match="max_leverage must be finite",
    ):
        PreTradeValidator(
            max_position_size=100,
            max_leverage=max_leverage,
        )


@pytest.mark.parametrize(
    "max_leverage",
    [
        True,
        False,
        "10",
        None,
        object(),
    ],
)
def test_non_numeric_max_leverage(
    max_leverage: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="max_leverage must be a number",
    ):
        PreTradeValidator(
            max_position_size=100,
            max_leverage=max_leverage,  # type: ignore[arg-type]
        )


def test_approved_result_factory() -> None:
    result = ValidationResult.approve()

    assert result.approved is True
    assert result.reason is None
    assert result.rejected is False


def test_rejected_result_factory_strips_reason() -> None:
    result = ValidationResult.reject(
        "  Rejected.  "
    )

    assert result.approved is False
    assert result.reason == "Rejected."
    assert result.rejected is True


def test_result_is_immutable() -> None:
    result = ValidationResult.approve()

    with pytest.raises(
        FrozenInstanceError,
    ):
        result.approved = False  # type: ignore[misc]


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
        ValidationResult(
            approved=approved,  # type: ignore[arg-type]
        )


def test_approved_result_rejects_reason() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "approved result must not "
            "have a reason"
        ),
    ):
        ValidationResult(
            approved=True,
            reason="Rejected.",
        )


@pytest.mark.parametrize(
    "reason",
    [
        None,
        "",
        " ",
        "\t",
        "\n",
    ],
)
def test_rejected_result_requires_reason(
    reason: str | None,
) -> None:
    with pytest.raises(
        ValueError,
        match=(
            "rejected result requires "
            "a reason"
        ),
    ):
        ValidationResult(
            approved=False,
            reason=reason,
        )


@pytest.mark.parametrize(
    "reason",
    [
        1,
        True,
        object(),
    ],
)
def test_result_rejects_invalid_reason_type(
    reason: object,
) -> None:
    with pytest.raises(
        TypeError,
        match=(
            "reason must be a string or None"
        ),
    ):
        ValidationResult(
            approved=False,
            reason=reason,  # type: ignore[arg-type]
        )


def test_rejection_reason_length_is_bounded() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "reason must not exceed "
            "500 characters"
        ),
    ):
        ValidationResult.reject(
            "x" * 501
        )


def test_result_types(
    validator: PreTradeValidator,
) -> None:
    result = validator.validate(
        position_size=10,
        leverage=5,
        entry_price=100,
        stop_loss=95,
    )

    assert type(result.approved) is bool
    assert result.reason is None