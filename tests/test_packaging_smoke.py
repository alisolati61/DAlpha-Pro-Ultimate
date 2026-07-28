"""Smoke tests for Phase 1A packaging and direct runtime dependencies."""

from importlib import import_module


def test_data_main_uses_a_package_import() -> None:
    module = import_module("src.data.main")

    assert module.MarketDataFeed.__module__ == "src.data.market_data_feed"


def test_pydantic_settings_is_importable() -> None:
    module = import_module("pydantic_settings")

    assert module.BaseSettings is not None


def test_websockets_is_importable() -> None:
    module = import_module("websockets")

    assert module.connect is not None
