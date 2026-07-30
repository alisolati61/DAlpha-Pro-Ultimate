# Legacy and Compatibility Boundaries

The repository grew through several architecture generations. This document
prevents older imports from being mistaken for the canonical recorded runtime.
Compatibility means "retained because a consumer or public test exists," not
"recommended for new code."

## Compatibility rules

1. New runtime composition uses the canonical module named below.
2. Existing compatibility imports remain unchanged during Phase 1H-1.
3. No legacy model is silently aliased to a canonical model with different
   validation or semantics.
4. Removal requires both in-repository and known external consumer evidence.
5. Frozen behavior is not reopened merely to simplify names.
6. Deprecation and migration occur in a separately reviewed Phase 1H-2 change.

## Entrypoints and configuration

| Compatibility surface | Canonical replacement | Notes |
| --- | --- | --- |
| Root `main.py` | Installed `alpha-pro-x` / `src.cli:main` | Thin wrapper; safe to retain |
| `src.core.kernel.bootstrap.bootstrap()` | `build_runtime()` | Compatibility helper returns only an initialized kernel |
| `src.data.main` | Explicit `MarketDataService` composition | Import-safe factory, not an application entry point |
| `src.config.settings` | `src.core.config` for Doctor/runtime | Legacy `BaseSettings` reads environment/`.env`; not used by readiness |
| `requirements/*.txt` | `pyproject.toml` | Convenience lists are incomplete and unbounded |

The legacy settings module is still consumed by `src.exchange.bingx_websocket`.
It cannot be removed until that consumer is migrated or formally deprecated.
The BingX readiness script supplies configuration from allowlisted CLI input and
`getpass`; it never imports this settings module.

## Runtime contracts

| Parallel/compatibility surface | Canonical current surface | Migration constraint |
| --- | --- | --- |
| `src.core.contracts.service.IService` | `src.core.lifecycle.service.Service` | Public contract imports/tests must move |
| Other `src.core.contracts.*` interfaces | Concrete core config/event bus/registry/lifecycle modules | Confirm external consumers before removal |
| `src.execution.paper_trading.PaperTradingEngine` | `src.paper_runtime.PaperExecutionCoordinator` | APIs and fill/state semantics differ |
| `src.execution_intent.validation.FrozenExecutionValidationAdapter` | No replacement; intentional compatibility adapter | Retain while execution-intent relies on frozen execution validation |
| `src.interfaces.exchange_interface.ExchangeInterface` and sync drivers | Frozen async exchange/client surfaces or injected runtime protocols | Requires async consumer migration; do not bridge with threads |

The frozen execution and exchange libraries are canonical libraries, but they
are not automatically wired into Doctor or the recorded runtime.

## Market data

| Module | Status | Known role |
| --- | --- | --- |
| `src.data.market_data.MarketData` | Canonical | Recorded/local top-of-book snapshot |
| `src.data.adapters.models.RecordedMarketDataPayload` | Canonical | Sequence-controlled replay envelope |
| `src.paper_runtime.models.PaperMarketEvent` | Canonical | Paper fill-driving event |
| `src.domain.market_data.MarketData` | Compatibility/legacy | Used by `src.data.normalizer` and tests |
| `src.market.market_data.MarketData` | Compatibility/legacy | Used by older analysis/intelligence/scoring consumers |
| `src.data.normalizer` | Compatibility/legacy | Produces the domain legacy model |
| `src.market.normalizer` | Confirmed dead in-repository | No consumers; retain until removal review |

These models have different fields and invariants. Consolidation requires
explicit adapters and consumer tests; a search-and-replace migration is unsafe.

## Decision and analytics

The frozen recorded path is `src.strategy` followed by
`src.decision.recorded`/`src.decision.replay` with an injected
`src.risk.RiskOrchestrator`.

The following are not that path:

- `src.analysis.decision_engine` - test-consumed compatibility analysis API;
- `src.decision.decision_engine` and `src.decision.models` - exported/tested
  older decision API;
- `src.core.decision_engine` - no in-repository consumer;
- `src.ai.decision_engine_old`, `market_regime_old`, `scoring_engine_old`, and
  `strategy_selector_old` - confirmed dead legacy modules;
- AI, analysis, and core `market_regime.py` modules - incompatible parallel
  engines used by different older consumers;
- intelligence trend/watchlist engines - deferred/legacy graphs, not recorded
  runtime services.

Some analysis basename pairs, such as ICT and Smart Money order blocks, fair
value gaps, and breaker blocks, are intentional namespace-specific algorithms,
not duplicate files to merge blindly.

## Value objects

`src.domain.value_objects` and `src.shared.value_objects` both expose money,
price, quantity, and symbol concepts. The domain versions are the current
hardened domain types. Shared versions remain public/test-consumed
compatibility types. They have separate semantics and must not be aliased until
consumer migration and serialization compatibility are proven.

## Empty and dead files

Empty package `__init__.py` files remain legitimate markers because removing
them may change setuptools discovery, Python package identity, or pytest import
behavior. Empty feature modules, `_old.py` files, typo artifacts, and
zero-consumer modules are classified in
[REPOSITORY_AUDIT.md](REPOSITORY_AUDIT.md). Phase 1H-1 documents them; it does
not treat their names as implemented capabilities.

## Phase 1H-2 migration sequence

1. Freeze an external-consumer inventory.
2. Approve canonical product/package naming.
3. Add explicit adapters and deprecation warnings where contracts differ.
4. Migrate tests and production consumers by family.
5. Prove import, serialization, lifecycle, and deterministic-output
   compatibility.
6. Remove only the reviewed dead set.
7. Run the full pytest, Ruff, mypy, compile, build, and import-safety gates.

No step may alter frozen risk, signing, request ordering, execution, paper-fill,
or VST reconciliation behavior.
