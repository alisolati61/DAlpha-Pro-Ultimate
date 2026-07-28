"""Tests for defensive raw-candle validation."""

from __future__ import annotations

from decimal import Decimal

import pytest

from src.data.data_validator import (
    DataValidator,
    ValidationResult,
)


def valid_candle() -> list[list[object]]:
    return [
        [
            1,
            100,
            110,
            90,
            105,
            1000,
        ]
    ]


def test_valid_batch_preserves_public_contract() -> None:
    result = DataValidator().validate(valid_candle())

    assert isinstance(result, ValidationResult)
    assert result.valid is True
    assert result.reason == "OK"


def test_extra_exchange_fields_are_allowed() -> None:
    candles = valid_candle()
    candles[0].extend(["extra", 42])

    assert DataValidator().validate(candles) == ValidationResult(
        True,
        "OK",
    )


def test_tuple_batches_and_tuple_candles_are_supported() -> None:
    candles = ((1, 100, 110, 90, 105, 1000),)

    assert DataValidator().validate(candles).valid is True


def test_numeric_strings_and_decimal_values_are_supported() -> None:
    candles = [
        [
            1,
            "100",
            Decimal("110"),
            "90",
            Decimal("105"),
            "1000",
        ]
    ]

    assert DataValidator().validate(candles).valid is True


@pytest.mark.parametrize(
    ("candles", "reason"),
    [
        (None, "Invalid candle collection"),
        ("not-a-batch", "Invalid candle collection"),
        (b"not-a-batch", "Invalid candle collection"),
        (object(), "Invalid candle collection"),
        ([], "Empty candle list"),
        ([None], "Invalid candle format"),
        (["bad-candle"], "Invalid candle format"),
        ([[1, 2, 3]], "Invalid candle format"),
    ],
)
def test_invalid_collection_or_format_is_non_throwing(
    candles: object,
    reason: str,
) -> None:
    result = DataValidator().validate(candles)  # type: ignore[arg-type]

    assert result == ValidationResult(False, reason)


@pytest.mark.parametrize(
    "value",
    [
        None,
        object(),
        "",
        "not-a-number",
        True,
        False,
        float("nan"),
        float("inf"),
        float("-inf"),
    ],
)
def test_invalid_numeric_values_are_non_throwing(
    value: object,
) -> None:
    candles = valid_candle()
    candles[0][1] = value

    assert DataValidator().validate(candles) == ValidationResult(
        False,
        "Invalid candle values",
    )


def test_high_lower_than_low_keeps_legacy_reason() -> None:
    result = DataValidator().validate(
        [[1, 100, 90, 110, 100, 100]]
    )

    assert result == ValidationResult(
        False,
        "High lower than Low",
    )


@pytest.mark.parametrize(
    ("candle", "reason"),
    [
        ([1, 0, 110, 90, 100, 1], "Non-positive price"),
        ([1, 100, 110, 0, 100, 1], "Non-positive price"),
        ([1, 200, 110, 90, 100, 1], "Open outside range"),
        ([1, 100, 110, 90, 200, 1], "Close outside range"),
        ([1, 100, 110, 90, 100, -1], "Negative volume"),
    ],
)
def test_invalid_ohlcv_relationships(
    candle: list[object],
    reason: str,
) -> None:
    assert DataValidator().validate([candle]) == ValidationResult(
        False,
        reason,
    )


def test_zero_volume_is_valid() -> None:
    candles = valid_candle()
    candles[0][5] = 0

    assert DataValidator().validate(candles).valid is True


def test_first_invalid_candle_stops_the_batch() -> None:
    candles = [
        [1, 100, 110, 90, 105, 10],
        [2, 100, 110, 90, 105, -1],
        [3, 100, 90, 110, 105, 10],
    ]

    assert DataValidator().validate(candles) == ValidationResult(
        False,
        "Negative volume",
    )


def test_validation_does_not_mutate_input() -> None:
    candles = valid_candle()
    snapshot = [row.copy() for row in candles]

    DataValidator().validate(candles)

    assert candles == snapshot


def test_result_fields_keep_stable_types() -> None:
    result = DataValidator().validate(valid_candle())

    assert isinstance(result.valid, bool)
    assert isinstance(result.reason, str)