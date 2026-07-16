import pytest

from src.exchange.connectors.crypto_connector import CryptoConnector


@pytest.mark.asyncio
async def test_crypto_connector():

    connector = CryptoConnector("bingx")

    assert connector.exchange is not None

    assert connector.exchange.exchange is not None