import pytest

from src.risk.pre_trade_validator import PreTradeValidator


@pytest.fixture
def validator():
    return PreTradeValidator(
        max_position_size=10,
        max_leverage=20,
    )


def test_valid_trade(validator):
    result = validator.validate(
        position_size=2,
        leverage=5,
        entry_price=100,
        stop_loss=95,
    )

    assert result.approved


def test_invalid_position_size(validator):
    result = validator.validate(
        position_size=100,
        leverage=5,
        entry_price=100,
        stop_loss=95,
    )

    assert not result.approved


def test_invalid_leverage(validator):
    result = validator.validate(
        position_size=2,
        leverage=50,
        entry_price=100,
        stop_loss=95,
    )

    assert not result.approved


def test_invalid_stop_loss(validator):
    result = validator.validate(
        position_size=2,
        leverage=5,
        entry_price=100,
        stop_loss=100,
    )

    assert not result.approved