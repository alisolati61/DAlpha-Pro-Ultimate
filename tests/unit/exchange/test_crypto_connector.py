import pytest

pytest.importorskip("ccxt.async_support")

from src.exchange.connectors.crypto_connector import (
    CryptoConnector,
)


def test_create():

    connector = CryptoConnector()

    assert connector is not None


def test_exchange():

    connector = CryptoConnector()

    assert connector.exchange is not None