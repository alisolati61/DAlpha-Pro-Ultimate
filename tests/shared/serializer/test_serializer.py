import pytest

from src.shared.serializer import JsonSerializer
from src.shared.serializer.exceptions import SerializationError


def test_dump():

    serializer = JsonSerializer()

    value = serializer.dumps({"price": 100})

    assert isinstance(value, str)


def test_load():

    serializer = JsonSerializer()

    value = serializer.loads('{"price":100}')

    assert value["price"] == 100


def test_invalid_json():

    serializer = JsonSerializer()

    with pytest.raises(SerializationError):
        serializer.loads("{invalid json}")