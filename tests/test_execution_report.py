"""Tests for immutable and validated execution reports."""

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta, timezone
from fractions import Fraction
from math import inf, nan

import pytest

from src.execution.execution_report import (
    ExecutionReport,
    ExecutionReportFactory,
)


FIXED_TIME = datetime(
    2026,
    7,
    25,
    12,
    30,
    tzinfo=UTC,
)


def test_success_report() -> None:
    report = ExecutionReportFactory.success(
        order_id="order-123",
        symbol="BTC/USDT",
        quantity=0.5,
        price=50_000,
    )

    assert isinstance(
        report,
        ExecutionReport,
    )
    assert report.order_id == "order-123"
    assert report.symbol == "BTC/USDT"
    assert report.success is True
    assert report.failed is False
    assert report.quantity == 0.5
    assert report.executed_price == 50_000.0
    assert report.message == "Order executed."
    assert report.timestamp.tzinfo == UTC


def test_failed_report() -> None:
    report = ExecutionReportFactory.failed(
        symbol="BTC/USDT",
        message="Insufficient balance.",
    )

    assert report.order_id == ""
    assert report.symbol == "BTC/USDT"
    assert report.success is False
    assert report.failed is True
    assert report.quantity == 0.0
    assert report.executed_price == 0.0
    assert report.message == "Insufficient balance."
    assert report.timestamp.tzinfo == UTC


def test_success_report_normalizes_strings() -> None:
    report = ExecutionReportFactory.success(
        order_id="  order-1  ",
        symbol="  BTC/USDT  ",
        quantity=1,
        price=100,
    )

    assert report.order_id == "order-1"
    assert report.symbol == "BTC/USDT"


def test_failed_report_normalizes_strings() -> None:
    report = ExecutionReportFactory.failed(
        symbol="  BTC/USDT  ",
        message="  Failed  ",
    )

    assert report.symbol == "BTC/USDT"
    assert report.message == "Failed"


def test_success_accepts_fixed_timestamp() -> None:
    report = ExecutionReportFactory.success(
        order_id="order-1",
        symbol="BTCUSDT",
        quantity=1,
        price=100,
        timestamp=FIXED_TIME,
    )

    assert report.timestamp is FIXED_TIME


def test_failed_accepts_fixed_timestamp() -> None:
    report = ExecutionReportFactory.failed(
        symbol="BTCUSDT",
        message="Rejected",
        timestamp=FIXED_TIME,
    )

    assert report.timestamp is FIXED_TIME


def test_non_utc_timestamp_is_normalized_to_utc() -> None:
    source_timestamp = datetime(
        2026,
        7,
        25,
        15,
        30,
        tzinfo=timezone(
            timedelta(hours=3)
        ),
    )

    report = ExecutionReportFactory.success(
        order_id="order-1",
        symbol="BTCUSDT",
        quantity=1,
        price=100,
        timestamp=source_timestamp,
    )

    assert report.timestamp == FIXED_TIME
    assert report.timestamp.tzinfo is UTC


@pytest.mark.parametrize(
    "factory_name",
    [
        "success",
        "failed",
    ],
)
def test_naive_timestamp_is_rejected(
    factory_name: str,
) -> None:
    timestamp = datetime(
        2026,
        7,
        25,
        12,
        30,
    )

    with pytest.raises(
        ValueError,
        match="timestamp must be timezone-aware",
    ):
        if factory_name == "success":
            ExecutionReportFactory.success(
                order_id="order-1",
                symbol="BTCUSDT",
                quantity=1,
                price=100,
                timestamp=timestamp,
            )
        else:
            ExecutionReportFactory.failed(
                symbol="BTCUSDT",
                message="Rejected",
                timestamp=timestamp,
            )


@pytest.mark.parametrize(
    "timestamp",
    [
        True,
        1,
        "2026-07-25",
        object(),
    ],
)
def test_invalid_timestamp_type_is_rejected(
    timestamp: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="timestamp must be a datetime",
    ):
        ExecutionReportFactory.failed(
            symbol="BTCUSDT",
            message="Rejected",
            timestamp=timestamp,  # type: ignore[arg-type]
        )


def test_report_is_immutable() -> None:
    report = ExecutionReportFactory.success(
        order_id="order-1",
        symbol="BTC/USDT",
        quantity=1,
        price=100,
    )

    with pytest.raises(
        FrozenInstanceError,
    ):
        report.success = False  # type: ignore[misc]


def test_notional_value_for_success() -> None:
    report = ExecutionReportFactory.success(
        order_id="order-1",
        symbol="BTCUSDT",
        quantity=2.5,
        price=100,
    )

    assert report.notional_value == 250.0
    assert type(report.notional_value) is float


def test_notional_value_for_failure_is_zero() -> None:
    report = ExecutionReportFactory.failed(
        symbol="BTCUSDT",
        message="Rejected",
    )

    assert report.notional_value == 0.0


def test_direct_construction_remains_permissive() -> None:
    report = ExecutionReport(
        order_id="order-1",
        symbol="BTCUSDT",
        success=True,
        quantity=0.0,
        executed_price=0.0,
        message="Raw external report.",
        timestamp=FIXED_TIME,
    )

    assert report.quantity == 0.0
    assert report.executed_price == 0.0


@pytest.mark.parametrize(
    "quantity",
    [
        0,
        -1,
    ],
)
def test_success_rejects_invalid_quantity(
    quantity: float,
) -> None:
    with pytest.raises(
        ValueError,
        match="quantity must be greater than zero",
    ):
        ExecutionReportFactory.success(
            order_id="order-1",
            symbol="BTC/USDT",
            quantity=quantity,
            price=100,
        )


@pytest.mark.parametrize(
    "price",
    [
        0,
        -1,
    ],
)
def test_success_rejects_invalid_price(
    price: float,
) -> None:
    with pytest.raises(
        ValueError,
        match="price must be greater than zero",
    ):
        ExecutionReportFactory.success(
            order_id="order-1",
            symbol="BTC/USDT",
            quantity=1,
            price=price,
        )


@pytest.mark.parametrize(
    "value",
    [
        nan,
        inf,
        -inf,
    ],
)
def test_success_rejects_non_finite_quantity(
    value: float,
) -> None:
    with pytest.raises(
        ValueError,
        match="quantity must be finite",
    ):
        ExecutionReportFactory.success(
            order_id="order-1",
            symbol="BTC/USDT",
            quantity=value,
            price=100,
        )


@pytest.mark.parametrize(
    "value",
    [
        nan,
        inf,
        -inf,
    ],
)
def test_success_rejects_non_finite_price(
    value: float,
) -> None:
    with pytest.raises(
        ValueError,
        match="price must be finite",
    ):
        ExecutionReportFactory.success(
            order_id="order-1",
            symbol="BTC/USDT",
            quantity=1,
            price=value,
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
def test_success_rejects_invalid_quantity_type(
    value: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="quantity must be a real number",
    ):
        ExecutionReportFactory.success(
            order_id="order-1",
            symbol="BTC/USDT",
            quantity=value,  # type: ignore[arg-type]
            price=100,
        )


@pytest.mark.parametrize(
    "value",
    [
        True,
        False,
        "100",
        None,
        object(),
    ],
)
def test_success_rejects_invalid_price_type(
    value: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="price must be a real number",
    ):
        ExecutionReportFactory.success(
            order_id="order-1",
            symbol="BTC/USDT",
            quantity=1,
            price=value,  # type: ignore[arg-type]
        )


def test_fraction_numeric_values_are_supported() -> None:
    report = ExecutionReportFactory.success(
        order_id="order-1",
        symbol="BTCUSDT",
        quantity=Fraction(1, 2),
        price=Fraction(100, 1),
    )

    assert report.quantity == 0.5
    assert report.executed_price == 100.0


@pytest.mark.parametrize(
    "order_id",
    [
        "",
        " ",
        "\t",
        "\n",
    ],
)
def test_success_rejects_empty_order_id(
    order_id: str,
) -> None:
    with pytest.raises(
        ValueError,
        match="order_id cannot be empty",
    ):
        ExecutionReportFactory.success(
            order_id=order_id,
            symbol="BTC/USDT",
            quantity=1,
            price=100,
        )


@pytest.mark.parametrize(
    "symbol",
    [
        "",
        " ",
        "\t",
        "\n",
    ],
)
def test_success_rejects_empty_symbol(
    symbol: str,
) -> None:
    with pytest.raises(
        ValueError,
        match="symbol cannot be empty",
    ):
        ExecutionReportFactory.success(
            order_id="order-1",
            symbol=symbol,
            quantity=1,
            price=100,
        )


@pytest.mark.parametrize(
    "symbol",
    [
        "",
        " ",
        "\t",
        "\n",
    ],
)
def test_failed_rejects_empty_symbol(
    symbol: str,
) -> None:
    with pytest.raises(
        ValueError,
        match="symbol cannot be empty",
    ):
        ExecutionReportFactory.failed(
            symbol=symbol,
            message="Failed",
        )


@pytest.mark.parametrize(
    "message",
    [
        "",
        " ",
        "\t",
        "\n",
    ],
)
def test_failed_rejects_empty_message(
    message: str,
) -> None:
    with pytest.raises(
        ValueError,
        match="message cannot be empty",
    ):
        ExecutionReportFactory.failed(
            symbol="BTC/USDT",
            message=message,
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        (
            "order_id",
            None,
        ),
        (
            "symbol",
            None,
        ),
    ],
)
def test_success_rejects_invalid_string_types(
    field: str,
    value: object,
) -> None:
    arguments: dict[str, object] = {
        "order_id": "order-1",
        "symbol": "BTCUSDT",
        "quantity": 1,
        "price": 100,
    }
    arguments[field] = value

    with pytest.raises(
        TypeError,
        match=f"{field} must be a string",
    ):
        ExecutionReportFactory.success(
            **arguments,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        (
            "symbol",
            None,
        ),
        (
            "message",
            None,
        ),
    ],
)
def test_failed_rejects_invalid_string_types(
    field: str,
    value: object,
) -> None:
    arguments: dict[str, object] = {
        "symbol": "BTCUSDT",
        "message": "Rejected",
    }
    arguments[field] = value

    with pytest.raises(
        TypeError,
        match=f"{field} must be a string",
    ):
        ExecutionReportFactory.failed(
            **arguments,  # type: ignore[arg-type]
        )


def test_order_id_length_is_bounded() -> None:
    with pytest.raises(
        ValueError,
        match="order_id must not exceed 200 characters",
    ):
        ExecutionReportFactory.success(
            order_id="x" * 201,
            symbol="BTCUSDT",
            quantity=1,
            price=100,
        )


def test_symbol_length_is_bounded() -> None:
    with pytest.raises(
        ValueError,
        match="symbol must not exceed 100 characters",
    ):
        ExecutionReportFactory.success(
            order_id="order-1",
            symbol="x" * 101,
            quantity=1,
            price=100,
        )


def test_failure_message_length_is_bounded() -> None:
    with pytest.raises(
        ValueError,
        match="message must not exceed 500 characters",
    ):
        ExecutionReportFactory.failed(
            symbol="BTCUSDT",
            message="x" * 501,
        )


def test_maximum_string_lengths_are_accepted() -> None:
    success = ExecutionReportFactory.success(
        order_id="x" * 200,
        symbol="S" * 100,
        quantity=1,
        price=100,
    )
    failure = ExecutionReportFactory.failed(
        symbol="S" * 100,
        message="x" * 500,
    )

    assert len(success.order_id) == 200
    assert len(success.symbol) == 100
    assert len(failure.message) == 500


def test_report_state_types() -> None:
    report = ExecutionReportFactory.success(
        order_id="order-1",
        symbol="BTC/USDT",
        quantity=1,
        price=100,
    )

    assert type(report.order_id) is str
    assert type(report.symbol) is str
    assert type(report.success) is bool
    assert type(report.quantity) is float
    assert type(report.executed_price) is float
    assert type(report.message) is str
    assert isinstance(report.timestamp, datetime)


def test_timestamp_is_timezone_aware() -> None:
    report = ExecutionReportFactory.success(
        order_id="order-1",
        symbol="BTC/USDT",
        quantity=1,
        price=100,
    )

    assert report.timestamp.tzinfo is not None
    assert report.timestamp.utcoffset() is not None