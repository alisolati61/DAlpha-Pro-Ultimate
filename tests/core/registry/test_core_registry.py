import pytest

from src.core.registry.registry import Registry
from src.core.registry.exceptions import (
    AlreadyRegisteredError,
    NotRegisteredError,
)


def test_register():
    registry = Registry()

    obj = object()

    registry.register("service", obj)

    assert registry.get("service") is obj


def test_exists():
    registry = Registry()

    registry.register("x", object())

    assert registry.exists("x")


def test_unregister():
    registry = Registry()

    registry.register("x", object())

    registry.unregister("x")

    assert not registry.exists("x")


def test_duplicate_registration():
    registry = Registry()

    registry.register("a", object())

    with pytest.raises(AlreadyRegisteredError):
        registry.register("a", object())


def test_missing():
    registry = Registry()

    with pytest.raises(NotRegisteredError):
        registry.get("missing")


def test_clear():
    registry = Registry()

    registry.register("a", object())
    registry.register("b", object())

    registry.clear()

    assert registry.size == 0