from datetime import UTC, datetime

import pytest

from src.execution.execution_report import (
    ExecutionReport,
    ExecutionReportFactory,
)


def test_success_report():

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

    assert report.order_id == (
        "order-123"
    )

    assert report.symbol == (
        "BTC/USDT"
    )

    assert report.success is True

    assert report.quantity == 0.5

    assert report.executed_price == (
        50_000.0
    )

    assert report.message == (
        "Order executed."
    )

    assert isinstance(
        report.timestamp,
        datetime,
    )

    assert (
        report.timestamp.tzinfo
        == UTC
    )


def test_failed_report():

    report = ExecutionReportFactory.failed(
        symbol="BTC/USDT",
        message="Insufficient balance.",
    )

    assert isinstance(
        report,
        ExecutionReport,
    )

    assert report.order_id == ""

    assert report.symbol == (
        "BTC/USDT"
    )

    assert report.success is False

    assert report.quantity == 0.0

    assert report.executed_price == 0.0

    assert report.message == (
        "Insufficient balance."
    )

    assert (
        report.timestamp.tzinfo
        == UTC
    )


def test_success_report_normalizes_strings():

    report = ExecutionReportFactory.success(
        order_id="  order-1  ",
        symbol="  BTC/USDT  ",
        quantity=1,
        price=100,
    )

    assert report.order_id == "order-1"

    assert report.symbol == "BTC/USDT"


def test_failed_report_normalizes_strings():

    report = ExecutionReportFactory.failed(
        symbol="  BTC/USDT  ",
        message="  Failed  ",
    )

    assert report.symbol == "BTC/USDT"

    assert report.message == "Failed"


def test_report_is_immutable():

    report = ExecutionReportFactory.success(
        order_id="order-1",
        symbol="BTC/USDT",
        quantity=1,
        price=100,
    )

    with pytest.raises(
        AttributeError,
    ):

        report.success = False


@pytest.mark.parametrize(
    "quantity",
    [
        0,
        -1,
    ],
)
def test_success_rejects_invalid_quantity(
    quantity,
):

    with pytest.raises(
        ValueError,
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
    price,
):

    with pytest.raises(
        ValueError,
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
        float("nan"),
        float("inf"),
        float("-inf"),
    ],
)
def test_success_rejects_invalid_quantity_values(
    value,
):

    with pytest.raises(
        ValueError,
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
        float("nan"),
        float("inf"),
        float("-inf"),
    ],
)
def test_success_rejects_invalid_price_values(
    value,
):

    with pytest.raises(
        ValueError,
    ):

        ExecutionReportFactory.success(
            order_id="order-1",
            symbol="BTC/USDT",
            quantity=1,
            price=value,
        )


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
    order_id,
):

    with pytest.raises(
        ValueError,
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
    symbol,
):

    with pytest.raises(
        ValueError,
    ):

        ExecutionReportFactory.success(
            order_id="order-1",
            symbol=symbol,
            quantity=1,
            price=100,
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
    message,
):

    with pytest.raises(
        ValueError,
    ):

        ExecutionReportFactory.failed(
            symbol="BTC/USDT",
            message=message,
        )


def test_failed_rejects_empty_symbol():

    with pytest.raises(
        ValueError,
    ):

        ExecutionReportFactory.failed(
            symbol="",
            message="Failed",
        )


def test_success_rejects_invalid_order_id_type():

    with pytest.raises(
        TypeError,
    ):

        ExecutionReportFactory.success(
            order_id=None,
            symbol="BTC/USDT",
            quantity=1,
            price=100,
        )


def test_success_rejects_invalid_symbol_type():

    with pytest.raises(
        TypeError,
    ):

        ExecutionReportFactory.success(
            order_id="order-1",
            symbol=None,
            quantity=1,
            price=100,
        )


def test_failed_rejects_invalid_message_type():

    with pytest.raises(
        TypeError,
    ):

        ExecutionReportFactory.failed(
            symbol="BTC/USDT",
            message=None,
        )


def test_report_state_types():

    report = ExecutionReportFactory.success(
        order_id="order-1",
        symbol="BTC/USDT",
        quantity=1,
        price=100,
    )

    assert isinstance(
        report.order_id,
        str,
    )

    assert isinstance(
        report.symbol,
        str,
    )

    assert isinstance(
        report.success,
        bool,
    )

    assert isinstance(
        report.quantity,
        float,
    )

    assert isinstance(
        report.executed_price,
        float,
    )

    assert isinstance(
        report.message,
        str,
    )

    assert isinstance(
        report.timestamp,
        datetime,
    )


def test_failed_report_has_zero_execution_values():

    report = ExecutionReportFactory.failed(
        symbol="ETH/USDT",
        message="Rejected",
    )

    assert report.quantity == 0.0

    assert report.executed_price == 0.0

    assert report.order_id == ""


def test_timestamp_is_timezone_aware():

    report = ExecutionReportFactory.success(
        order_id="order-1",
        symbol="BTC/USDT",
        quantity=1,
        price=100,
    )

    assert (
        report.timestamp.tzinfo
        is not None
    )

    assert (
        report.timestamp.utcoffset()
        is not None
    )