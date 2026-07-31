"""Regression coverage for the bounded Phase 1H-2 removal manifest."""

from __future__ import annotations

from importlib.util import find_spec
from pathlib import Path

import pytest

_REMOVED_MODULES = (
    "src.ai.decision_engine_old",
    "src.ai.market_regime_old",
    "src.ai.scoring_engine_old",
    "src.ai.strategy_selector_old",
    "src.analysis.indicators.macd",
    "src.analysis.onchain.whales",
    "src.analysis.technical.anchored_vwap",
    "src.analysis.technical.channel",
    "src.analysis.technical.pivot",
    "src.analysis.technical.trendline",
    "src.config.constants",
    "src.core.contracts.interfaces",
    "src.exchange.connectors.init",
    "src.infrastructure.base_connector",
    "src.infrastructure.exchange_connector",
    "src.infrastructure.connectors.failover",
    "src.infrastructure.connectors.news_connector",
    "src.infrastructure.connectors.onchain_connector",
    "src.infrastructure.connectors.sentiment_connector",
    "src.infrastructure.connectors.websocket_connector",
)

_REMOVED_NON_MODULE_PATHS = (
    "src/exchange/compliance",
    "src/exchange/interfaces",
    "src/exchange/rest",
    "test_exchange.py",
)

_SUPPORTED_IMPORTS = (
    "src.ai.market_regime",
    "src.analysis.onchain.whale_tracker",
    "src.analysis.technical.macd",
    "src.cli",
    "src.exchange.connectors.crypto_connector",
)


@pytest.mark.parametrize("module_name", _REMOVED_MODULES)
def test_removed_dead_module_is_not_importable(module_name: str) -> None:
    assert find_spec(module_name) is None


@pytest.mark.parametrize("relative_path", _REMOVED_NON_MODULE_PATHS)
def test_removed_dead_non_module_path_is_absent(relative_path: str) -> None:
    repository_root = Path(__file__).resolve().parents[1]

    assert not (repository_root / relative_path).exists()


@pytest.mark.parametrize("module_name", _SUPPORTED_IMPORTS)
def test_supported_neighbor_remains_importable(module_name: str) -> None:
    assert find_spec(module_name) is not None
