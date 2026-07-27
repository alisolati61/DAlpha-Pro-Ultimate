"""Compatibility tests for the final market-data validator.

Invalid states are injected deliberately with ``object.__setattr__`` because
``MarketData`` is now an immutable validated boundary object. This keeps the
validator tests meaningful without weakening the production model.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from src.data.market_data import MarketData
from src.data.validator import (
    MarketDataValidator,
    ValidationResult,
)


def make() -> MarketData:
    return MarketData(
        symbol="BTCUSDT",
        exchange="Binance",
        timeframe="1m",
        price=100,
        bid=99,
        ask=101,
        volume=10,
        timestamp=datetime.now(UTC),
    )


def corrupt(
    data: MarketData,
    **changes: Any,
) -> MarketData:
    """Inject an invalid legacy/corrupted state for validator testing."""

    for field_name, value in changes.items():
        object.__setattr__(data, field_name, value)

    return data


def test_valid() -> None:
    result = MarketDataValidator().validate(make())

    assert isinstance(result, ValidationResult)
    assert result.valid is True
    assert result.reason == "OK"


@pytest.mark.parametrize(
    ("changes", "reason"),
    [
        ({"price": 0}, "Invalid price"),
        ({"bid": 0}, "Invalid bid"),
        ({"ask": 0}, "Invalid ask"),
        (
            {"bid": 110, "ask": 100},
            "Bid greater than Ask",
        ),
        ({"volume": -1}, "Negative volume"),
    ],
)
def test_invalid_legacy_state_is_rejected(
    changes: dict[str, Any],
    reason: str,
) -> None:
    data = corrupt(make(), **changes)

    result = MarketDataValidator().validate(data)

    assert result.valid is False
    assert result.reason == reason


def test_result_fields_have_stable_types() -> None:
    result = MarketDataValidator().validate(make())

    assert isinstance(result.valid, bool)
    assert isinstance(result.reason, str)