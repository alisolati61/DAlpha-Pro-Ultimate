import pytest

from src.risk.position_sizer import (
    PositionSizeResult,
    PositionSizer,
)


def test_calculates_one_percent_risk():

    result = PositionSizer.calculate_position_size(
        balance=10_000,
        risk_percent=1,
        entry_price=100,
        stop_loss=95,
    )

    assert isinstance(
        result,
        PositionSizeResult,
    )

    assert result.risk_amount == 100.0

    assert result.stop_distance == 5.0

    assert result.position_size == 20.0


def test_calculates_fractional_position_size():

    result = PositionSizer.calculate_position_size(
        balance=10_000,
        risk_percent=2,
        entry_price=100,
        stop_loss=97.5,
    )

    assert result.risk_amount == 200.0

    assert result.stop_distance == 2.5

    assert result.position_size == 80.0


def test_supports_stop_above_entry():

    result = PositionSizer.calculate_position_size(
        balance=10_000,
        risk_percent=1,
        entry_price=100,
        stop_loss=105,
    )

    assert result.stop_distance == 5.0

    assert result.position_size == 20.0


@pytest.mark.parametrize(
    "balance",
    [0, -1],
)
def test_invalid_balance(balance):

    with pytest.raises(
        ValueError,
        match="Balance must be greater than zero",
    ):

        PositionSizer.calculate_position_size(
            balance=balance,
            risk_percent=1,
            entry_price=100,
            stop_loss=95,
        )


@pytest.mark.parametrize(
    "risk_percent",
    [0, -1],
)
def test_invalid_risk_percent(risk_percent):

    with pytest.raises(
        ValueError,
        match="Risk percent must be greater than zero",
    ):

        PositionSizer.calculate_position_size(
            balance=10_000,
            risk_percent=risk_percent,
            entry_price=100,
            stop_loss=95,
        )


def test_risk_percent_cannot_exceed_one_hundred():

    with pytest.raises(
        ValueError,
        match="Risk percent cannot exceed 100",
    ):

        PositionSizer.calculate_position_size(
            balance=10_000,
            risk_percent=100.01,
            entry_price=100,
            stop_loss=95,
        )


@pytest.mark.parametrize(
    "entry_price",
    [0, -1],
)
def test_invalid_entry_price(entry_price):

    with pytest.raises(
        ValueError,
        match="Entry price must be greater than zero",
    ):

        PositionSizer.calculate_position_size(
            balance=10_000,
            risk_percent=1,
            entry_price=entry_price,
            stop_loss=95,
        )


@pytest.mark.parametrize(
    "stop_loss",
    [0, -1],
)
def test_invalid_stop_loss(stop_loss):

    with pytest.raises(
        ValueError,
        match="Stop-loss price must be greater than zero",
    ):

        PositionSizer.calculate_position_size(
            balance=10_000,
            risk_percent=1,
            entry_price=100,
            stop_loss=stop_loss,
        )


def test_zero_stop_distance():

    with pytest.raises(
        ValueError,
        match="Stop distance must be greater than zero",
    ):

        PositionSizer.calculate_position_size(
            balance=10_000,
            risk_percent=1,
            entry_price=100,
            stop_loss=100,
        )


def test_result_types():

    result = PositionSizer.calculate_position_size(
        balance=10_000,
        risk_percent=1,
        entry_price=100,
        stop_loss=95,
    )

    assert isinstance(
        result.position_size,
        float,
    )

    assert isinstance(
        result.risk_amount,
        float,
    )

    assert isinstance(
        result.stop_distance,
        float,
    )