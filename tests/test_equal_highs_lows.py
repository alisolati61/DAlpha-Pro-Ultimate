"""Tests for equal-high and equal-low detection."""

from dataclasses import FrozenInstanceError
from math import inf, nan

import pytest

from src.analysis.smart_money.equal_highs_lows import (
    EqualHighLowEngine,
    EqualHighLowResult,
)


def test_default_configuration() -> None:
    engine = EqualHighLowEngine()

    assert engine.absolute_tolerance == 0.0
    assert engine.relative_tolerance == 0.0


def test_accepts_valid_configuration() -> None:
    engine = EqualHighLowEngine(
        absolute_tolerance=2,
        relative_tolerance=0.01,
    )

    assert engine.absolute_tolerance == 2.0
    assert engine.relative_tolerance == 0.01


@pytest.mark.parametrize(
    ("name", "kwargs"),
    [
        (
            "absolute_tolerance",
            {"absolute_tolerance": -0.01},
        ),
        (
            "relative_tolerance",
            {"relative_tolerance": -0.01},
        ),
    ],
)
def test_rejects_negative_tolerance(
    name: str,
    kwargs: dict[str, float],
) -> None:
    with pytest.raises(
        ValueError,
        match=rf"{name} must be greater than or equal to zero",
    ):
        EqualHighLowEngine(**kwargs)


def test_rejects_relative_tolerance_above_one() -> None:
    with pytest.raises(
        ValueError,
        match="relative_tolerance must be between 0.0 and 1.0",
    ):
        EqualHighLowEngine(
            relative_tolerance=1.01,
        )


@pytest.mark.parametrize(
    ("name", "kwargs"),
    [
        (
            "absolute_tolerance",
            {"absolute_tolerance": "1"},
        ),
        (
            "absolute_tolerance",
            {"absolute_tolerance": None},
        ),
        (
            "absolute_tolerance",
            {"absolute_tolerance": True},
        ),
        (
            "relative_tolerance",
            {"relative_tolerance": "0.1"},
        ),
        (
            "relative_tolerance",
            {"relative_tolerance": None},
        ),
        (
            "relative_tolerance",
            {"relative_tolerance": False},
        ),
    ],
)
def test_rejects_non_numeric_tolerance(
    name: str,
    kwargs: dict[str, object],
) -> None:
    with pytest.raises(
        TypeError,
        match=rf"{name} must be a real number",
    ):
        EqualHighLowEngine(
            **kwargs,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    ("name", "kwargs"),
    [
        (
            "absolute_tolerance",
            {"absolute_tolerance": nan},
        ),
        (
            "absolute_tolerance",
            {"absolute_tolerance": inf},
        ),
        (
            "relative_tolerance",
            {"relative_tolerance": -inf},
        ),
    ],
)
def test_rejects_non_finite_tolerance(
    name: str,
    kwargs: dict[str, float],
) -> None:
    with pytest.raises(
        ValueError,
        match=rf"{name} must be finite",
    ):
        EqualHighLowEngine(**kwargs)


def test_detects_exact_equal_high_only() -> None:
    result = EqualHighLowEngine().detect(
        previous_high=110.0,
        previous_low=100.0,
        current_high=110.0,
        current_low=101.0,
    )

    assert result == EqualHighLowResult(
        equal_high=True,
        equal_low=False,
        high_price=110.0,
        low_price=None,
    )

    assert result.valid is True
    assert result.both is False
    assert result.liquidity_level_count == 1


def test_detects_exact_equal_low_only() -> None:
    result = EqualHighLowEngine().detect(
        previous_high=110.0,
        previous_low=100.0,
        current_high=111.0,
        current_low=100.0,
    )

    assert result == EqualHighLowResult(
        equal_high=False,
        equal_low=True,
        high_price=None,
        low_price=100.0,
    )


def test_detects_both_equal_levels() -> None:
    result = EqualHighLowEngine().detect(
        previous_high=110.0,
        previous_low=100.0,
        current_high=110.0,
        current_low=100.0,
    )

    assert result.equal_high is True
    assert result.equal_low is True
    assert result.high_price == 110.0
    assert result.low_price == 100.0
    assert result.valid is True
    assert result.both is True
    assert result.liquidity_level_count == 2


def test_returns_invalid_result_when_no_levels_are_equal() -> None:
    result = EqualHighLowEngine().detect(
        previous_high=110.0,
        previous_low=100.0,
        current_high=112.0,
        current_low=102.0,
    )

    assert result == EqualHighLowResult(
        equal_high=False,
        equal_low=False,
        high_price=None,
        low_price=None,
    )

    assert result.valid is False
    assert result.both is False
    assert result.liquidity_level_count == 0


def test_absolute_tolerance_is_inclusive() -> None:
    result = EqualHighLowEngine(
        absolute_tolerance=0.5,
    ).detect(
        previous_high=110.0,
        previous_low=100.0,
        current_high=110.5,
        current_low=101.0,
    )

    assert result.equal_high is True
    assert result.high_price == 110.5


def test_difference_above_absolute_tolerance_is_rejected() -> None:
    result = EqualHighLowEngine(
        absolute_tolerance=0.5,
    ).detect(
        previous_high=110.0,
        previous_low=100.0,
        current_high=110.5001,
        current_low=101.0,
    )

    assert result.equal_high is False
    assert result.high_price is None


def test_relative_tolerance_is_inclusive() -> None:
    result = EqualHighLowEngine(
        relative_tolerance=0.01,
    ).detect(
        previous_high=99.0,
        previous_low=80.0,
        current_high=100.0,
        current_low=82.0,
    )

    assert result.equal_high is True
    assert result.high_price == 100.0


def test_difference_above_relative_tolerance_is_rejected() -> None:
    result = EqualHighLowEngine(
        relative_tolerance=0.01,
    ).detect(
        previous_high=98.99,
        previous_low=80.0,
        current_high=100.0,
        current_low=82.0,
    )

    assert result.equal_high is False


def test_larger_of_absolute_and_relative_tolerance_is_used() -> None:
    result = EqualHighLowEngine(
        absolute_tolerance=0.25,
        relative_tolerance=0.01,
    ).detect(
        previous_high=99.2,
        previous_low=80.0,
        current_high=100.0,
        current_low=82.0,
    )

    assert result.equal_high is True


def test_equal_high_uses_outer_boundary() -> None:
    result = EqualHighLowEngine(
        absolute_tolerance=1.0,
    ).detect(
        previous_high=110.0,
        previous_low=90.0,
        current_high=110.75,
        current_low=92.0,
    )

    assert result.high_price == 110.75


def test_equal_low_uses_outer_boundary() -> None:
    result = EqualHighLowEngine(
        absolute_tolerance=1.0,
    ).detect(
        previous_high=120.0,
        previous_low=100.75,
        current_high=118.0,
        current_low=100.0,
    )

    assert result.low_price == 100.0


def test_integer_prices_are_normalized_to_float() -> None:
    result = EqualHighLowEngine().detect(
        previous_high=110,
        previous_low=100,
        current_high=110,
        current_low=101,
    )

    assert result.high_price == 110.0
    assert isinstance(result.high_price, float)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("previous_high", "110"),
        ("previous_low", None),
        ("current_high", True),
        ("current_low", object()),
    ],
)
def test_rejects_non_numeric_price(
    field: str,
    value: object,
) -> None:
    arguments: dict[str, object] = {
        "previous_high": 110.0,
        "previous_low": 100.0,
        "current_high": 111.0,
        "current_low": 101.0,
    }

    arguments[field] = value

    with pytest.raises(
        TypeError,
        match=rf"{field} must be a real number",
    ):
        EqualHighLowEngine().detect(
            **arguments,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("previous_high", nan),
        ("previous_low", inf),
        ("current_high", -inf),
        ("current_low", nan),
    ],
)
def test_rejects_non_finite_price(
    field: str,
    value: float,
) -> None:
    arguments = {
        "previous_high": 110.0,
        "previous_low": 100.0,
        "current_high": 111.0,
        "current_low": 101.0,
    }

    arguments[field] = value

    with pytest.raises(
        ValueError,
        match=rf"{field} must be finite",
    ):
        EqualHighLowEngine().detect(
            **arguments,
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("previous_high", 0.0),
        ("previous_low", -1.0),
        ("current_high", 0.0),
        ("current_low", -0.01),
    ],
)
def test_rejects_non_positive_price(
    field: str,
    value: float,
) -> None:
    arguments = {
        "previous_high": 110.0,
        "previous_low": 100.0,
        "current_high": 111.0,
        "current_low": 101.0,
    }

    arguments[field] = value

    with pytest.raises(
        ValueError,
        match=rf"{field} must be greater than zero",
    ):
        EqualHighLowEngine().detect(
            **arguments,
        )


def test_rejects_invalid_previous_range() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "previous_high must be greater than or equal "
            "to previous_low"
        ),
    ):
        EqualHighLowEngine().detect(
            previous_high=99.0,
            previous_low=100.0,
            current_high=110.0,
            current_low=101.0,
        )


def test_rejects_invalid_current_range() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "current_high must be greater than or equal "
            "to current_low"
        ),
    ):
        EqualHighLowEngine().detect(
            previous_high=110.0,
            previous_low=100.0,
            current_high=99.0,
            current_low=101.0,
        )


def test_accepts_zero_range_market_values() -> None:
    result = EqualHighLowEngine().detect(
        previous_high=100.0,
        previous_low=100.0,
        current_high=100.0,
        current_low=100.0,
    )

    assert result.equal_high is True
    assert result.equal_low is True


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("equal_high", 1),
        ("equal_low", "False"),
    ],
)
def test_result_rejects_non_boolean_flags(
    field: str,
    value: object,
) -> None:
    arguments: dict[str, object] = {
        "equal_high": True,
        "equal_low": False,
        "high_price": 110.0,
        "low_price": None,
    }

    arguments[field] = value

    with pytest.raises(
        TypeError,
        match=rf"{field} must be a bool",
    ):
        EqualHighLowResult(
            **arguments,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    (
        "equal_high",
        "equal_low",
        "high_price",
        "low_price",
        "message",
    ),
    [
        (
            True,
            False,
            None,
            None,
            "high_price is required when equal_high is true",
        ),
        (
            False,
            True,
            None,
            None,
            "low_price is required when equal_low is true",
        ),
        (
            False,
            False,
            110.0,
            None,
            "high_price must be None when equal_high is false",
        ),
        (
            False,
            False,
            None,
            100.0,
            "low_price must be None when equal_low is false",
        ),
    ],
)
def test_result_protects_flag_and_price_invariants(
    equal_high: bool,
    equal_low: bool,
    high_price: float | None,
    low_price: float | None,
    message: str,
) -> None:
    with pytest.raises(
        ValueError,
        match=message,
    ):
        EqualHighLowResult(
            equal_high=equal_high,
            equal_low=equal_low,
            high_price=high_price,
            low_price=low_price,
        )


def test_result_rejects_high_price_below_low_price() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "high_price must be greater than or equal "
            "to low_price"
        ),
    ):
        EqualHighLowResult(
            equal_high=True,
            equal_low=True,
            high_price=99.0,
            low_price=100.0,
        )


@pytest.mark.parametrize(
    ("field", "value", "error", "message"),
    [
        (
            "high_price",
            "110",
            TypeError,
            "high_price must be a real number",
        ),
        (
            "low_price",
            nan,
            ValueError,
            "low_price must be finite",
        ),
        (
            "high_price",
            0.0,
            ValueError,
            "high_price must be greater than zero",
        ),
    ],
)
def test_result_validates_detected_prices(
    field: str,
    value: object,
    error: type[Exception],
    message: str,
) -> None:
    arguments: dict[str, object] = {
        "equal_high": True,
        "equal_low": True,
        "high_price": 110.0,
        "low_price": 100.0,
    }

    arguments[field] = value

    with pytest.raises(
        error,
        match=message,
    ):
        EqualHighLowResult(
            **arguments,  # type: ignore[arg-type]
        )


def test_result_is_immutable() -> None:
    result = EqualHighLowResult(
        equal_high=True,
        equal_low=False,
        high_price=110.0,
        low_price=None,
    )

    with pytest.raises(FrozenInstanceError):
        result.high_price = 111.0  # type: ignore[misc]