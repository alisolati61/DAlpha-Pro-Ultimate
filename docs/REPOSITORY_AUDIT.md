# Repository Audit

Audit baseline: branch `phase-1h-repository-hardening` at
`vst-runtime-freeze-v1`.

The audit inspected the tracked tree, package/tool configuration, runtime entry
points, frozen tags, exact imports/references, pytest discovery, duplicate
basenames, byte-identical files, and ignored local artifacts. "No consumer"
means no in-repository import/reference was found; external consumers remain a
separate removal risk.

## Classification vocabulary

- **Legitimate package marker:** empty `__init__.py` retained for package,
  setuptools, or pytest import identity.
- **Canonical implementation:** current supported module for its documented
  namespace and role.
- **Compatibility-only:** retained for public/test/legacy consumers; not the
  current recorded runtime.
- **Unsupported scaffold:** incomplete and not a supported capability.
- **Confirmed dead code:** no in-repository consumer and no current supported
  role.
- **Requires consumer migration before removal:** parallel contract with known
  consumers or materially different semantics.

## Empty Python files

There are 74 tracked semantically empty Python files.

### Legitimate package markers (58)

All files in this list are classified **legitimate package marker** and remain:

```text
src/__init__.py
src/analysis/derivatives/__init__.py
src/analysis/intermarket/__init__.py
src/analysis/onchain/__init__.py
src/analysis/orderflow/__init__.py
src/analysis/sentiment/__init__.py
src/analysis/technical/__init__.py
src/config/__init__.py
src/core/__init__.py
src/core/event_bus/__init__.py
src/infrastructure/connectors/__init__.py
src/intelligence/analyzers/__init__.py
src/intelligence/trend_discovery/__init__.py
src/intelligence/watchlist/__init__.py
src/market/__init__.py
tests/__init__.py
tests/core/__init__.py
tests/core/context/__init__.py
tests/core/contracts/__init__.py
tests/core/dependency_injection/__init__.py
tests/core/event_bus/__init__.py
tests/core/exceptions/__init__.py
tests/core/kernel/__init__.py
tests/core/lifecycle/__init__.py
tests/core/registry/__init__.py
tests/core/types/__init__.py
tests/domain/__init__.py
tests/domain/entities/__init__.py
tests/domain/events/__init__.py
tests/domain/value_objects/__init__.py
tests/integration/decision/__init__.py
tests/integration/execution_intent/__init__.py
tests/manual/__init__.py
tests/shared/__init__.py
tests/shared/clock/__init__.py
tests/shared/ids/__init__.py
tests/shared/mapper/__init__.py
tests/shared/result/__init__.py
tests/shared/serializer/__init__.py
tests/shared/validators/__init__.py
tests/shared/value_objects/__init__.py
tests/unit/__init__.py
tests/unit/ai/__init__.py
tests/unit/analysis/__init__.py
tests/unit/backtest/__init__.py
tests/unit/core/__init__.py
tests/unit/data/__init__.py
tests/unit/decision/__init__.py
tests/unit/decision/recorded/__init__.py
tests/unit/decision/strategy/__init__.py
tests/unit/domain/__init__.py
tests/unit/drivers/__init__.py
tests/unit/exchange/__init__.py
tests/unit/execution/__init__.py
tests/unit/execution_intent/__init__.py
tests/unit/paper_runtime/__init__.py
tests/unit/risk/__init__.py
tests/unit/strategy/__init__.py
```

### Empty feature/scaffold files (16)

| Classification | Paths | Consumer evidence |
| --- | --- | --- |
| Unsupported scaffold | `src/analysis/indicators/macd.py`; `src/analysis/onchain/whales.py`; `src/analysis/technical/anchored_vwap.py`; `channel.py`; `pivot.py`; `trendline.py` | Empty; zero exact imports/references |
| Unsupported scaffold | `src/config/constants.py`; `src/core/contracts/interfaces.py` | Empty; zero exact imports/references |
| Unsupported scaffold | `src/infrastructure/base_connector.py`; `src/infrastructure/exchange_connector.py` | Empty; zero exact imports/references |
| Unsupported scaffold | `src/infrastructure/connectors/failover.py`; `news_connector.py`; `onchain_connector.py`; `sentiment_connector.py`; `websocket_connector.py` | Empty; zero exact imports/references |
| Confirmed dead code | `src/exchange/connectors/init.py` | Empty, misnamed (not `__init__.py`), zero consumers |

Short abstract/Protocol method bodies, exception marker classes, and tested
no-op lifecycle methods were inspected and are not counted as placeholders.
No implemented module contained a TODO/FIXME placeholder claim.

## Non-Python zero-byte files

| File | Classification | Disposition |
| --- | --- | --- |
| `src/exchange/compliance` | Unsupported scaffold | Unimportable, zero consumers; retained for Phase 1H-2 review |
| `src/exchange/interfaces` | Unsupported scaffold | Unimportable, zero consumers; retained for Phase 1H-2 review |
| `src/exchange/rest` | Unsupported scaffold | Unimportable, zero consumers; retained for Phase 1H-2 review |
| `src/core/contracts/interfaces.pypwd` | Confirmed dead code | Typo/editor artifact, zero consumers; removed in Phase 1H-1 under the generated-temporary exception |

## `_old.py` inventory

All four files have zero in-repository imports/references:

| File | Classification |
| --- | --- |
| `src/ai/decision_engine_old.py` | Confirmed dead code |
| `src/ai/market_regime_old.py` | Confirmed dead code |
| `src/ai/scoring_engine_old.py` | Confirmed dead code |
| `src/ai/strategy_selector_old.py` | Confirmed dead code |

They are not generated artifacts, so Phase 1H-1 retains them.

## Duplicate basenames

There are 79 basename groups: 33 production groups and 47 test groups, with
`__init__.py` shared by both counts. SHA-256 comparison found no byte-identical
non-empty tracked files.

### Production groups (33)

| Basename | Classification and finding |
| --- | --- |
| `__init__.py` | Legitimate package markers or intentional package export surfaces; not duplicate implementations |
| `base.py` | Core exception and frozen exchange bases are canonical; unexported `src/domain/base.py` is confirmed dead code |
| `breaker_block.py` | ICT and Smart Money analyzers are namespace-distinct canonical implementations |
| `configuration.py` | Core contract and older AlphaError exception are compatibility-only; current config errors live under `src.core.config` |
| `coordinator.py` | Paper and VST coordinators are separate canonical frozen runtimes |
| `decision_engine.py` | Analysis and exported decision engines are compatibility-only; core engine is confirmed dead; canonical recorded path is `src.decision.recorded`/`replay`; consumer migration is required before consolidation |
| `engine.py` | Trend-discovery engine is compatibility-only; watchlist engine is confirmed dead |
| `errors.py` | Core config/services, data/data-adapter, and VST taxonomies are canonical namespace-local implementations; shared validator errors are compatibility-only |
| `event_bus.py` | Core implementation is canonical; core contract interface is compatibility-only |
| `exceptions.py` | Namespace-local canonical/compatibility taxonomies; zero-consumer context, domain entity/general, mapper, and validator exception modules are confirmed dead |
| `fair_value_gap.py` | ICT and Smart Money analyzers are namespace-distinct canonical implementations |
| `logger.py` | Concrete logger is canonical for its older logger package; core logger contract is compatibility-only |
| `macd.py` | `src.analysis.technical.macd` is canonical; empty indicators version is an unsupported scaffold |
| `main.py` | Root wrapper and `src.data.main` are compatibility-only; canonical CLI is `src.cli:main` |
| `market_data.py` | `src.data.market_data` is canonical; domain and market models require consumer migration before removal |
| `market_regime.py` | AI, analysis, and core regimes are incompatible parallel legacy/deferred contracts; consumer migration required |
| `market_structure.py` | Smart Money analyzer and canonical strategy implementation occupy different layers; both are canonical in their namespace |
| `models.py` | Core config/diagnostics/services, data adapter, exchange, strategy, execution-intent, paper, and VST models are canonical package contracts; decision models are compatibility-only |
| `money.py` | Domain value is canonical; shared public/test value requires consumer migration |
| `normalizer.py` | Data normalizer is compatibility-only and emits the legacy domain model; market normalizer is confirmed dead |
| `order_block.py` | ICT and Smart Money analyzers are namespace-distinct canonical implementations |
| `price.py` | Domain value is canonical; shared public/test value requires consumer migration |
| `quantity.py` | Domain value is canonical; shared public/test value requires consumer migration |
| `reconciliation.py` | Paper and VST reconcilers are separate canonical frozen implementations |
| `recorded.py` | Data adapter and decision service are separate consecutive canonical pipeline stages |
| `registry.py` | Core implementation is canonical; core contract and shared mapper registry are compatibility-only |
| `result.py` | Generic shared result and validator result are distinct compatibility-only contracts |
| `service.py` | Core lifecycle, data, strategy, and execution-intent services are canonical; core `IService` is compatibility-only |
| `state.py` | Kernel and lifecycle states are distinct canonical internal contracts |
| `symbol.py` | Domain value is canonical; shared public/test value requires consumer migration |
| `types.py` | Event-bus and registry types are distinct canonical internals |
| `validation.py` | Core exception is compatibility-only; execution-intent validation is an intentional compatibility adapter to frozen execution |
| `validator.py` | Data validator is canonical; infrastructure connector and shared generic validators are compatibility-only |

### Test groups (47 including `__init__.py`)

`__init__.py` files are legitimate package markers. The following 46 repeated
test basenames are **canonical implementation** of distinct regression tests at
different package/test levels. None is byte-identical:

```text
test_backtest_engine.py
test_balance_tracker.py
test_base_exchange.py
test_breaker_block.py
test_circuit_breaker.py
test_decision_engine.py
test_drawdown_guard.py
test_event_bus.py
test_exceptions.py
test_execution_engine.py
test_execution_history.py
test_execution_manager.py
test_execution_report.py
test_fair_value_gap.py
test_in_trade_monitor.py
test_kill_switch.py
test_lifecycle.py
test_macd.py
test_market_data.py
test_market_regime.py
test_models.py
test_monte_carlo.py
test_order_block.py
test_order_manager.py
test_order_tracker.py
test_paper_trading.py
test_parameter_optimizer.py
test_portfolio_guard.py
test_portfolio_manager.py
test_portfolio_sync.py
test_position_manager.py
test_position_sizer.py
test_pre_trade_validator.py
test_reconnect.py
test_report_generator.py
test_risk_manager.py
test_risk_orchestrator.py
test_rsi.py
test_security.py
test_slippage.py
test_smart_router.py
test_statistics_engine.py
test_strategy_runner.py
test_trade_simulator.py
test_validator.py
test_walk_forward.py
```

Same basename does not mean redundant coverage; Phase 1H-2 may reorganize tests
only after comparing behavior and collection identity.

## Scripts and entrypoints

| File | Classification | Finding |
| --- | --- | --- |
| `src.cli` / `alpha-pro-x` | Canonical implementation | Doctor-only supported CLI |
| `main.py` | Compatibility-only | Thin wrapper to canonical CLI |
| `scripts/bingx_vst_readiness.py` | Canonical implementation | Manual, getpass-only, read-only, directly unit tested |
| `scripts/bingx_vst_transport_diagnostic.py` | Canonical implementation | Public server-time only, directly unit tested |
| `test_exchange.py` | Confirmed dead code | Obsolete live CCXT/BingX ticker script, zero consumers, outside `testpaths=["tests"]`; retained because it is not generated |
| `src.data.main` | Compatibility-only | Import-safe factory, not a deployed command |

The root live-network script must never be invoked by CI.

## Generated and temporary artifacts

### Tracked at audit start

| File | Classification | Evidence/disposition |
| --- | --- | --- |
| `bject Name, Length` | Confirmed dead code | Malformed command-output filename, contains only three tag names, zero consumers; removed in Phase 1H-1 |
| `project_audit_snapshot.txt` | Confirmed dead code | Generated Git/file/test snapshot, begins with `=== GIT STATUS ===`, zero consumers; removed in Phase 1H-1 |
| `src/core/contracts/interfaces.pypwd` | Confirmed dead code | Zero-byte typo/editor artifact, zero consumers; removed in Phase 1H-1 |

These are the only deletions in this phase and satisfy the allowed
"proven generated temporary artifact with zero consumers" condition.

### Ignored local/generated families observed

| Family | Classification |
| --- | --- |
| `__pycache__/`, `*.pyc` | Generated interpreter cache |
| `.pytest_cache/`, `.pytest-tmp/`, `.hypothesis/` | Generated test state |
| `.mypy_cache/`, `.ruff_cache/` | Generated static-tool state |
| `.coverage*`, `htmlcov/`, `coverage.xml` | Generated coverage output |
| `build/`, `dist/`, `*.egg-info/`, `*.whl` | Generated package output |
| `.venv/`, `venv/`, `env/` | Local environments |
| `.vscode/`, `.idea/`, editor swap/backup files | Local editor state |
| `logs/`, `*.log` | Local runtime logs |
| `.env` | Local sensitive configuration; never tracked |
| `readiness-output*.json` | Local sanitized manual output; ignored even though none was present |
| `*.db`, `*.sqlite`, `*.sqlite3` | Local database state |

Empty untracked local directories named `config/`, `data/`, and `tools/` are
not repository files and make no capability claim.

## Naming audit

| Concern | Current name |
| --- | --- |
| Repository/directory | `DAlpha-Pro-Ultimate` |
| Distribution | `alpha-pro-x-infinity` |
| CLI | `alpha-pro-x` |
| Import namespace | `src` |
| Runtime display name | `Alpha Pro X Infinity` |
| Legacy settings display name | `Alpha Pro UltimateX` |

### Recommended Phase 1H-2 plan

Choose **Alpha Pro X Infinity** as the product identity, then perform one
coordinated migration:

1. approve a repository slug such as `alpha-pro-x-infinity`;
2. retain `alpha-pro-x-infinity` as the distribution name;
3. retain `alpha-pro-x` as the short operator command;
4. replace the generic `src` import package with
   `alpha_pro_x_infinity`;
5. align runtime metadata and remove the legacy display-name variant;
6. ship temporary import/entrypoint shims with deprecation tests;
7. update packaging, docs, type checking, and consumers atomically.

Do not rename only one surface: partial renames would make imports and
deployment provenance less clear.

## Removal boundary

Phase 1H-1 removes only the three proven generated artifacts above. All
unsupported scaffolds, confirmed dead source modules, compatibility surfaces,
and consumer-migration families remain for an explicit Phase 1H-2 removal
manifest. No trading, risk, signing, transport, fill, or reconciliation code is
changed by this audit.
