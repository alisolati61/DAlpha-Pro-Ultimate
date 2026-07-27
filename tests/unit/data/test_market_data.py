"""Behavioral tests for validated market snapshots."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta, timezone

import pytest

from src.data.market_data import MarketData


def make_data(**overrides: object) -> MarketData:
    values: dict[str, object] = {
        "symbol": "BTCUSDT",
        "exchange": "Binance",
        "timeframe": "1m",
        "price": 100,
        "bid": 99,
        "ask": 101,
        "volume": 500,
        "timestamp": datetime(2026, 1, 1, tzinfo=UTC),
    }
    values.update(overrides)
    return MarketData(**values)  # type: ignore[arg-type]


def test_snapshot_normalizes_text_and_numeric_values() -> None:
    data = make_data(
        symbol=" BTCUSDT ",
        exchange=" Binance ",
        timeframe=" 1m ",
        price="100.5",
        bid="100",
        ask="101",
        volume="5.25",
    )

    assert data.symbol == "BTCUSDT"
    assert data.exchange == "Binance"
    assert data.timeframe == "1m"
    assert data.price == 100.5
    assert data.bid == 100.0
    assert data.ask == 101.0
    assert data.volume == 5.25


def test_spread_is_always_derived_from_bid_and_ask() -> None:
    data = make_data(
        bid=99,
        ask=101,
        spread=999,
    )

    assert data.spread == 2.0


def test_mid_price_and_spread_bps_are_consistent() -> None:
    data = make_data(
        bid=99,
        ask=101,
    )

    assert data.mid_price == 100.0
    assert data.spread_bps == 200.0


def test_zero_book_has_zero_spread_basis_points() -> None:
    data = make_data(
        bid=0,
        ask=0,
    )

    assert data.mid_price == 0.0
    assert data.spread == 0.0
    assert data.spread_bps == 0.0


def test_naive_timestamp_is_interpreted_as_utc() -> None:
    timestamp = datetime(2026, 1, 1, 12, 30)

    data = make_data(timestamp=timestamp)

    assert data.timestamp == timestamp.replace(tzinfo=UTC)
    assert data.timestamp.tzinfo is UTC


def test_aware_timestamp_is_converted_to_utc() -> None:
    local_timezone = timezone(timedelta(hours=3, minutes=30))
    timestamp = datetime(
        2026,
        1,
        1,
        12,
        30,
        tzinfo=local_timezone,
    )

    data = make_data(timestamp=timestamp)

    assert data.timestamp == datetime(
        2026,
        1,
        1,
        9,
        0,
        tzinfo=UTC,
    )
    assert data.timestamp.tzinfo is UTC


def test_snapshot_is_immutable() -> None:
    data = make_data()

    with pytest.raises(FrozenInstanceError):
        data.price = 200  # type: ignore[misc]


@pytest.mark.parametrize(
    ("field_name", "value", "message"),
    [
        ("symbol", "", "symbol cannot be empty"),
        ("symbol", "   ", "symbol cannot be empty"),
        ("exchange", "", "exchange cannot be empty"),
        ("timeframe", "", "timeframe cannot be empty"),
        ("symbol", 123, "symbol must be a string"),
    ],
)
def test_invalid_text_fields_are_rejected(
    field_name: str,
    value: object,
    message: str,
) -> None:
    with pytest.raises(
        (TypeError, ValueError),
        match=message,
    ):
        make_data(**{field_name: value})


@pytest.mark.parametrize(
    ("field_name", "value", "message"),
    [
        ("price", 0, "price must be greater than zero"),
        ("price", -1, "price must be greater than zero"),
        ("price", float("nan"), "price must be finite"),
        ("bid", float("inf"), "bid must be finite"),
        ("ask", float("-inf"), "ask must be finite"),
        ("volume", -1, "volume must be greater than or equal"),
        ("price", True, "price must be numeric"),
        ("bid", object(), "bid must be numeric"),
    ],
)
def test_invalid_numeric_values_are_rejected(
    field_name: str,
    value: object,
    message: str,
) -> None:
    with pytest.raises(
        (TypeError, ValueError),
        match=message,
    ):
        make_data(**{field_name: value})


def test_crossed_book_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="ask must be greater than or equal to bid",
    ):
        make_data(
            bid=101,
            ask=100,
        )


def test_timestamp_must_be_datetime() -> None:
    with pytest.raises(
        TypeError,
        match="timestamp must be a datetime",
    ):
        make_data(timestamp=1_700_000_000)


def test_slots_prevent_dynamic_attributes() -> None:
    data = make_data()

    with pytest.raises(
        (AttributeError, TypeError),
    ):
        object.__setattr__(data, "unexpected", 1)