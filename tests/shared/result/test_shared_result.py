import pytest

from src.shared.result import Success, Failure
from src.shared.result.exceptions import InvalidResultError
from src.shared.result.result import Result


def test_success():

    result = Success(100)

    assert result.is_success
    assert not result.is_failure
    assert result.value == 100


def test_failure():

    result = Failure("error")

    assert result.is_failure
    assert not result.is_success
    assert result.error == "error"


def test_invalid():

    with pytest.raises(InvalidResultError):
        Result()

    with pytest.raises(InvalidResultError):
        Result(value=1, error="bad")


def test_failure_value():

    result = Failure("bad")

    with pytest.raises(ValueError):
        _ = result.value


def test_success_error():

    result = Success(1)

    with pytest.raises(ValueError):
        _ = result.error