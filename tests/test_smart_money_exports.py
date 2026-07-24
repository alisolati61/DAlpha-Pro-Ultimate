"""Tests for the public smart-money package API."""

from __future__ import annotations

import src.analysis.smart_money as smart_money
from src.analysis.smart_money.bos import (
    BOSEngine,
    BOSResult,
)
from src.analysis.smart_money.breaker_block import (
    BreakerBlock,
    BreakerBlockEngine,
    BreakerRetestResult,
)
from src.analysis.smart_money.choch import (
    CHOCHEngine,
    CHOCHResult,
    TrendDirection,
)
from src.analysis.smart_money.equal_highs_lows import (
    EqualHighLowEngine,
    EqualHighLowResult,
)
from src.analysis.smart_money.fair_value_gap import (
    FairValueGap,
    FairValueGapEngine,
)
from src.analysis.smart_money.liquidity import (
    LiquidityEngine,
    LiquidityZone,
)
from src.analysis.smart_money.market_structure import (
    MarketStructure,
    MarketStructureEngine,
    SwingPoint,
    Trend,
)
from src.analysis.smart_money.mitigation import (
    InvalidationMode,
    MitigationEngine,
    MitigationResult,
)
from src.analysis.smart_money.order_block import (
    OrderBlock,
    OrderBlockEngine,
)


EXPECTED_EXPORTS = (
    "BOSEngine",
    "BOSResult",
    "BreakerBlock",
    "BreakerBlockEngine",
    "BreakerRetestResult",
    "CHOCHEngine",
    "CHOCHResult",
    "EqualHighLowEngine",
    "EqualHighLowResult",
    "FairValueGap",
    "FairValueGapEngine",
    "InvalidationMode",
    "LiquidityEngine",
    "LiquidityZone",
    "MarketStructure",
    "MarketStructureEngine",
    "MitigationEngine",
    "MitigationResult",
    "OrderBlock",
    "OrderBlockEngine",
    "SwingPoint",
    "Trend",
    "TrendDirection",
)


def test_public_exports_are_explicit_and_stable() -> None:
    assert smart_money.__all__ == EXPECTED_EXPORTS


def test_public_exports_have_no_duplicates() -> None:
    assert len(smart_money.__all__) == len(
        set(smart_money.__all__)
    )


def test_every_public_export_exists() -> None:
    for export_name in smart_money.__all__:
        assert hasattr(
            smart_money,
            export_name,
        ), f"missing smart-money export: {export_name}"


def test_engine_exports_reference_original_classes() -> None:
    assert smart_money.BOSEngine is BOSEngine
    assert smart_money.BreakerBlockEngine is BreakerBlockEngine
    assert smart_money.CHOCHEngine is CHOCHEngine
    assert smart_money.EqualHighLowEngine is EqualHighLowEngine
    assert smart_money.FairValueGapEngine is FairValueGapEngine
    assert smart_money.LiquidityEngine is LiquidityEngine
    assert smart_money.MarketStructureEngine is MarketStructureEngine
    assert smart_money.MitigationEngine is MitigationEngine
    assert smart_money.OrderBlockEngine is OrderBlockEngine


def test_result_exports_reference_original_classes() -> None:
    assert smart_money.BOSResult is BOSResult
    assert smart_money.BreakerBlock is BreakerBlock

    assert (
        smart_money.BreakerRetestResult
        is BreakerRetestResult
    )

    assert smart_money.CHOCHResult is CHOCHResult

    assert (
        smart_money.EqualHighLowResult
        is EqualHighLowResult
    )

    assert smart_money.FairValueGap is FairValueGap
    assert smart_money.LiquidityZone is LiquidityZone
    assert smart_money.MarketStructure is MarketStructure
    assert smart_money.MitigationResult is MitigationResult
    assert smart_money.OrderBlock is OrderBlock
    assert smart_money.SwingPoint is SwingPoint


def test_enum_and_type_alias_exports_reference_original_objects() -> None:
    assert smart_money.Trend is Trend

    assert (
        smart_money.TrendDirection
        is TrendDirection
    )

    assert (
        smart_money.InvalidationMode
        is InvalidationMode
    )


def test_wildcard_import_contains_only_public_exports() -> None:
    namespace: dict[str, object] = {}

    exec(
        "from src.analysis.smart_money import *",
        namespace,
    )

    imported_names = {
        name
        for name in namespace
        if not name.startswith("__")
    }

    assert imported_names == set(EXPECTED_EXPORTS)


def test_exported_engines_can_be_constructed() -> None:
    assert isinstance(
        smart_money.BOSEngine(),
        BOSEngine,
    )

    assert isinstance(
        smart_money.CHOCHEngine(),
        CHOCHEngine,
    )

    assert isinstance(
        smart_money.EqualHighLowEngine(),
        EqualHighLowEngine,
    )

    assert isinstance(
        smart_money.FairValueGapEngine(),
        FairValueGapEngine,
    )

    assert isinstance(
        smart_money.LiquidityEngine(),
        LiquidityEngine,
    )

    assert isinstance(
        smart_money.MarketStructureEngine(),
        MarketStructureEngine,
    )

    assert isinstance(
        smart_money.MitigationEngine(),
        MitigationEngine,
    )

    assert isinstance(
        smart_money.OrderBlockEngine(),
        OrderBlockEngine,
    )

    assert isinstance(
        smart_money.BreakerBlockEngine(),
        BreakerBlockEngine,
    )