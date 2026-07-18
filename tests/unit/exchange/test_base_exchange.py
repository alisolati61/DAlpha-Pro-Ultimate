import pytest

from src.exchange.base import BaseExchange


def test_cannot_instantiate():

    with pytest.raises(TypeError):

        BaseExchange()