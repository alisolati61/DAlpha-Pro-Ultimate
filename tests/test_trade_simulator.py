"""Tests for validated historical trade simulation."""

from dataclasses import FrozenInstanceError
from math import inf, nan

import pytest

from src.backtesting.trade_simulator import (
    TradeRequest,
    TradeSimulationResult,
    TradeSimulator,
)


def test_default_cost_configuration() -> None:
    request = TradeRequest(
        entry_price=100.0,
        exit_price=120.0,
        quantity=1.0,
    )

    assert request.commission == 0.0004
    assert request.slippage == 0.0002


def test_profitable_trade() -> None:
    result = TradeSimulator().simulate(
        TradeRequest(
            entry_price=100.0,
            exit_price=120.0,
            quantity=1.0,
        )
    )

    assert result == TradeSimulationResult(
        gross_profit=20.0,
        commission_paid=0.09,
        slippage_cost=0.04,
        net_profit=19.87,
        return_percent=19.87,
    )

    assert result.profitable is True
    assert result.unprofitable is False
    assert result.flat is False


def test_losing_trade() -> None:
    result = TradeSimulator().simulate(
        TradeRequest(
            entry_price=120.0,
            exit_price=100.0,
            quantity=1.0,
        )
    )

    assert result.gross_profit == -20.0
    assert result.commission_paid == 0.09
    assert result.slippage_cost == 0.04
    assert result.net_profit == -20.13
    assert result.return_percent == -16.77
    assert result.unprofitable is True


def test_flat_price_is_negative_after_costs() -> None:
    result = TradeSimulator().simulate(
        TradeRequest(
            entry_price=100.0,
            exit_price=100.0,
            quantity=1.0,
        )
    )

    assert result.gross_profit == 0.0
    assert result.net_profit == -0.12
    assert result.unprofitable is True


def test_zero_cost_flat_trade_is_flat() -> None:
    result = TradeSimulator().simulate(
        TradeRequest(
            entry_price=100.0,
            exit_price=100.0,
            quantity=1.0,
            commission=0.0,
            slippage=0.0,
        )
    )

    assert result.gross_profit == 0.0
    assert result.net_profit == 0.0
    assert result.return_percent == 0.0
    assert result.flat is True


def test_zero_quantity_preserves_existing_contract() -> None:
    result = TradeSimulator().simulate(
        TradeRequest(
            entry_price=100.0,
            exit_price=120.0,
            quantity=0.0,
        )
    )

    assert result.gross_profit == 0.0
    assert result.commission_paid == 0.0
    assert result.slippage_cost == 0.0
    assert result.net_profit == 0.0
    assert result.return_percent == 0.0


def test_commission_is_applied_to_round_trip_turnover() -> None:
    result = TradeSimulator().simulate(
        TradeRequest(
            entry_price=100.0,
            exit_price=110.0,
            quantity=2.0,
            commission=0.001,
            slippage=0.0,
        )
    )

    assert result.gross_profit == 20.0
    assert result.commission_paid == 0.42
    assert result.slippage_cost == 0.0
    assert result.net_profit == 19.58


def test_slippage_is_applied_to_round_trip_turnover() -> None:
    result = TradeSimulator().simulate(
        TradeRequest(
            entry_price=100.0,
            exit_price=110.0,
            quantity=2.0,
            commission=0.0,
            slippage=0.001,
        )
    )

    assert result.slippage_cost == 0.42
    assert result.net_profit == 19.58


def test_total_cost_property() -> None:
    result = TradeSimulator().simulate(
        TradeRequest(
            entry_price=100.0,
            exit_price=120.0,
            quantity=1.0,
        )
    )

    assert result.total_cost == 0.13


def test_request_notional_properties() -> None:
    request = TradeRequest(
        entry_price=100.0,
        exit_price=120.0,
        quantity=2.0,
    )

    assert request.entry_value == 200.0
    assert request.exit_value == 240.0
    assert request.turnover == 440.0


def test_integer_inputs_are_normalized_to_float() -> None:
    request = TradeRequest(
        entry_price=100,
        exit_price=120,
        quantity=2,
        commission=0,
        slippage=0,
    )

    assert request.entry_price == 100.0
    assert request.exit_price == 120.0
    assert request.quantity == 2.0
    assert isinstance(
        request.entry_price,
        float,
    )

    result = TradeSimulator().simulate(request)

    assert isinstance(
        result.gross_profit,
        float,
    )

    assert isinstance(
        result.commission_paid,
        float,
    )

    assert isinstance(
        result.slippage_cost,
        float,
    )

    assert isinstance(
        result.net_profit,
        float,
    )

    assert isinstance(
        result.return_percent,
        float,
    )


def test_money_and_percentage_values_are_rounded() -> None:
    result = TradeSimulator().simulate(
        TradeRequest(
            entry_price=100.0,
            exit_price=100.333,
            quantity=3.0,
            commission=0.0004,
            slippage=0.0002,
        )
    )

    assert result.gross_profit == 1.0
    assert result.commission_paid == 0.24
    assert result.slippage_cost == 0.12
    assert result.net_profit == 0.64
    assert result.return_percent == 0.21


def test_rejects_non_trade_request() -> None:
    with pytest.raises(
        TypeError,
        match="trade must be a TradeRequest instance",
    ):
        TradeSimulator().simulate(
            object(),  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        (
            "entry_price",
            "100",
        ),
        (
            "entry_price",
            True,
        ),
        (
            "exit_price",
            None,
        ),
        (
            "quantity",
            object(),
        ),
        (
            "commission",
            "0.001",
        ),
        (
            "slippage",
            False,
        ),
    ],
)
def test_request_rejects_non_numeric_values(
    field: str,
    value: object,
) -> None:
    arguments: dict[str, object] = {
        "entry_price": 100.0,
        "exit_price": 120.0,
        "quantity": 1.0,
        "commission": 0.0004,
        "slippage": 0.0002,
    }

    arguments[field] = value

    with pytest.raises(
        TypeError,
        match=rf"{field} must be a real number",
    ):
        TradeRequest(
            **arguments,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        (
            "entry_price",
            nan,
        ),
        (
            "exit_price",
            inf,
        ),
        (
            "quantity",
            -inf,
        ),
        (
            "commission",
            nan,
        ),
        (
            "slippage",
            inf,
        ),
    ],
)
def test_request_rejects_non_finite_values(
    field: str,
    value: float,
) -> None:
    arguments = {
        "entry_price": 100.0,
        "exit_price": 120.0,
        "quantity": 1.0,
        "commission": 0.0004,
        "slippage": 0.0002,
    }

    arguments[field] = value

    with pytest.raises(
        ValueError,
        match=rf"{field} must be finite",
    ):
        TradeRequest(**arguments)


@pytest.mark.parametrize(
    "field",
    [
        "entry_price",
        "exit_price",
    ],
)
@pytest.mark.parametrize(
    "value",
    [
        0.0,
        -1.0,
    ],
)
def test_request_rejects_non_positive_prices(
    field: str,
    value: float,
) -> None:
    arguments = {
        "entry_price": 100.0,
        "exit_price": 120.0,
        "quantity": 1.0,
    }

    arguments[field] = value

    with pytest.raises(
        ValueError,
        match=rf"{field} must be greater than zero",
    ):
        TradeRequest(**arguments)


def test_request_rejects_negative_quantity() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "quantity must be greater than "
            "or equal to zero"
        ),
    ):
        TradeRequest(
            entry_price=100.0,
            exit_price=120.0,
            quantity=-0.01,
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        (
            "commission",
            -0.001,
        ),
        (
            "commission",
            1.001,
        ),
        (
            "slippage",
            -0.001,
        ),
        (
            "slippage",
            1.001,
        ),
    ],
)
def test_request_rejects_out_of_range_rates(
    field: str,
    value: float,
) -> None:
    arguments = {
        "entry_price": 100.0,
        "exit_price": 120.0,
        "quantity": 1.0,
        "commission": 0.0004,
        "slippage": 0.0002,
    }

    arguments[field] = value

    with pytest.raises(
        ValueError,
        match=rf"{field} must be between 0.0 and 1.0",
    ):
        TradeRequest(**arguments)


@pytest.mark.parametrize(
    "field",
    [
        "entry_price",
        "exit_price",
        "quantity",
        "commission",
        "slippage",
    ],
)
def test_request_is_immutable(
    field: str,
) -> None:
    request = TradeRequest(
        entry_price=100.0,
        exit_price=120.0,
        quantity=1.0,
    )

    with pytest.raises(
        FrozenInstanceError,
    ):
        setattr(
            request,
            field,
            0.0,
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        (
            "gross_profit",
            "10",
        ),
        (
            "commission_paid",
            True,
        ),
        (
            "slippage_cost",
            None,
        ),
        (
            "net_profit",
            object(),
        ),
        (
            "return_percent",
            "5",
        ),
    ],
)
def test_result_rejects_non_numeric_values(
    field: str,
    value: object,
) -> None:
    arguments: dict[str, object] = {
        "gross_profit": 10.0,
        "commission_paid": 1.0,
        "slippage_cost": 1.0,
        "net_profit": 8.0,
        "return_percent": 8.0,
    }

    arguments[field] = value

    with pytest.raises(
        TypeError,
        match=rf"{field} must be a real number",
    ):
        TradeSimulationResult(
            **arguments,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        (
            "gross_profit",
            nan,
        ),
        (
            "commission_paid",
            inf,
        ),
        (
            "slippage_cost",
            -inf,
        ),
        (
            "net_profit",
            nan,
        ),
        (
            "return_percent",
            inf,
        ),
    ],
)
def test_result_rejects_non_finite_values(
    field: str,
    value: float,
) -> None:
    arguments = {
        "gross_profit": 10.0,
        "commission_paid": 1.0,
        "slippage_cost": 1.0,
        "net_profit": 8.0,
        "return_percent": 8.0,
    }

    arguments[field] = value

    with pytest.raises(
        ValueError,
        match=rf"{field} must be finite",
    ):
        TradeSimulationResult(**arguments)


@pytest.mark.parametrize(
    "field",
    [
        "commission_paid",
        "slippage_cost",
    ],
)
def test_result_rejects_negative_costs(
    field: str,
) -> None:
    arguments = {
        "gross_profit": 10.0,
        "commission_paid": 0.0,
        "slippage_cost": 0.0,
        "net_profit": 10.0,
        "return_percent": 10.0,
    }

    arguments[field] = -0.01

    with pytest.raises(
        ValueError,
        match=(
            rf"{field} must be greater than "
            rf"or equal to zero"
        ),
    ):
        TradeSimulationResult(**arguments)


def test_result_rejects_inconsistent_net_profit() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "net_profit must equal gross_profit "
            "minus trading costs"
        ),
    ):
        TradeSimulationResult(
            gross_profit=10.0,
            commission_paid=1.0,
            slippage_cost=1.0,
            net_profit=9.0,
            return_percent=9.0,
        )


@pytest.mark.parametrize(
    "field",
    [
        "gross_profit",
        "commission_paid",
        "slippage_cost",
        "net_profit",
        "return_percent",
    ],
)
def test_result_is_immutable(
    field: str,
) -> None:
    result = TradeSimulationResult(
        gross_profit=10.0,
        commission_paid=1.0,
        slippage_cost=1.0,
        net_profit=8.0,
        return_percent=8.0,
    )

    with pytest.raises(
        FrozenInstanceError,
    ):
        setattr(
            result,
            field,
            0.0,
        )