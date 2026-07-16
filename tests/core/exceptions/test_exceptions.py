import pytest

from src.core.exceptions import (
    AlphaError,
    CoreError,
    ValidationError,
    ConfigurationError,
)


def test_exception_inheritance():

    assert issubclass(CoreError, AlphaError)

    assert issubclass(ValidationError, AlphaError)

    assert issubclass(ConfigurationError, AlphaError)


def test_raise():

    with pytest.raises(AlphaError):

        raise CoreError()


def test_validation():

    with pytest.raises(ValidationError):

        raise ValidationError()


def test_configuration():

    with pytest.raises(ConfigurationError):

        raise ConfigurationError()