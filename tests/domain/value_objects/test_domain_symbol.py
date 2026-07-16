import pytest

from src.domain.value_objects import (
    Symbol,
    InvalidSymbolError,
)


def test_valid_symbol():

    symbol = Symbol("btcusdt")

    assert symbol.value == "BTCUSDT"


def test_strip_spaces():

    symbol = Symbol("  ethusdt ")

    assert symbol.value == "ETHUSDT"


def test_empty_symbol():

    with pytest.raises(InvalidSymbolError):
        Symbol("")


def test_invalid_symbol():

    with pytest.raises(InvalidSymbolError):
        Symbol("BTC/USDT")