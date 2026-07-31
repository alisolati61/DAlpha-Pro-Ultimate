# Repository Audit

Audit baseline: branch `phase-1h-repository-hardening`, frozen runtime at
`vst-runtime-freeze-v1`, with the bounded Phase 1H-2 cleanup applied.

The audit inspected the tracked tree, package/tool configuration, runtime entry
points, frozen tags, exact imports/references, pytest discovery, duplicate
basenames, byte-identical files, and ignored local artifacts. "No consumer"
means no in-repository import/reference was found; external consumers remain a
separate removal risk.

## Phase 1H-2 evidence and result

Every requested removal candidate was checked before deletion by:

1. parsing every tracked Python `Import` and `ImportFrom`, including resolved
   relative imports;
2. searching tracked Python, TOML, YAML, CLI, runtime, test, and documentation
   content for the path, stem, and dotted module name;
3. inspecting all dynamic-loading sites (`import_module`, `__import__`,
   `runpy`, package lazy exports, and plugin/discovery mechanisms);
4. inspecting the installed entry point and every `__main__` boundary;
5. checking Git history and all eight frozen tags;
6. confirming that documentation classified the candidate but did not require
   its API to remain.

For every removed source candidate the result was:
`static imports=0`, `dynamic imports=0`, `CLI/runtime references=0`,
`test dependencies=0`, and `required documentation contracts=0`.

### Removed source manifest (24 paths)

Confirmed-dead legacy modules:

```text
src/ai/decision_engine_old.py
src/ai/market_regime_old.py
src/ai/scoring_engine_old.py
src/ai/strategy_selector_old.py
```

Zero-byte unsupported Python scaffolds:

```text
src/analysis/indicators/macd.py
src/analysis/onchain/whales.py
src/analysis/technical/anchored_vwap.py
src/analysis/technical/channel.py
src/analysis/technical/pivot.py
src/analysis/technical/trendline.py
src/config/constants.py
src/core/contracts/interfaces.py
src/infrastructure/base_connector.py
src/infrastructure/exchange_connector.py
src/infrastructure/connectors/failover.py
src/infrastructure/connectors/news_connector.py
src/infrastructure/connectors/onchain_connector.py
src/infrastructure/connectors/sentiment_connector.py
src/infrastructure/connectors/websocket_connector.py
```

Misnamed/extensionless zero-byte scaffolds:

```text
src/exchange/connectors/init.py
src/exchange/compliance
src/exchange/interfaces
src/exchange/rest
```

Obsolete live-network script:

```text
test_exchange.py
```

The root script had no unique reusable logic. Its CCXT lifecycle and ticker
delegation already have injected-fake coverage in
`tests/unit/exchange/test_ccxt_exchange.py`; deletion removes an accidental
real-network hazard. `tests/test_repository_hygiene.py` now proves all removed
module/path names stay absent while supported neighboring imports remain
available.

All candidates originated in the initial `90527c8` commit except the empty
indicator MACD file, introduced empty in `4fa4426`; none was subsequently
maintained. Their ancestry in frozen tags did not make them an exported or
composed frozen contract.

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

Phase 1H-1 found 74 tracked semantically empty Python files. Phase 1H-2
removed the 16 zero-consumer non-markers. The remaining 58 are the legitimate
package markers below.

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

### Removed empty feature/scaffold files (16)

| Classification | Paths | Consumer evidence |
| --- | --- | --- |
| Unsupported scaffold, removed | `src/analysis/indicators/macd.py`; `src/analysis/onchain/whales.py`; `src/analysis/technical/anchored_vwap.py`; `channel.py`; `pivot.py`; `trendline.py` | Empty; zero static, dynamic, runtime, documentation, or test consumers |
| Unsupported scaffold, removed | `src/config/constants.py`; `src/core/contracts/interfaces.py` | Empty; zero static, dynamic, runtime, documentation, or test consumers |
| Unsupported scaffold, removed | `src/infrastructure/base_connector.py`; `src/infrastructure/exchange_connector.py` | Empty; zero static, dynamic, runtime, documentation, or test consumers |
| Unsupported scaffold, removed | `src/infrastructure/connectors/failover.py`; `news_connector.py`; `onchain_connector.py`; `sentiment_connector.py`; `websocket_connector.py` | Empty; zero static, dynamic, runtime, documentation, or test consumers |
| Confirmed dead code, removed | `src/exchange/connectors/init.py` | Empty, misnamed (not `__init__.py`), zero consumers |

Short abstract/Protocol method bodies, exception marker classes, and tested
no-op lifecycle methods were inspected and are not counted as placeholders.
No implemented module contained a TODO/FIXME placeholder claim.

## Non-Python zero-byte files

| File | Classification | Disposition |
| --- | --- | --- |
| `src/exchange/compliance` | Unsupported scaffold | Unimportable, zero consumers; removed in Phase 1H-2 |
| `src/exchange/interfaces` | Unsupported scaffold | Unimportable, zero consumers; removed in Phase 1H-2 |
| `src/exchange/rest` | Unsupported scaffold | Unimportable, zero consumers; removed in Phase 1H-2 |
| `src/core/contracts/interfaces.pypwd` | Confirmed dead code | Typo/editor artifact, zero consumers; removed in Phase 1H-1 under the generated-temporary exception |

## `_old.py` inventory

All four files had zero in-repository imports/references and were removed:

| File | Classification |
| --- | --- |
| `src/ai/decision_engine_old.py` | Confirmed dead code; removed in Phase 1H-2 |
| `src/ai/market_regime_old.py` | Confirmed dead code; removed in Phase 1H-2 |
| `src/ai/scoring_engine_old.py` | Confirmed dead code; removed in Phase 1H-2 |
| `src/ai/strategy_selector_old.py` | Confirmed dead code; removed in Phase 1H-2 |

Their similarly named classes in active tests resolve to `src.analysis`,
`src.core`, or `src.decision`, never these deleted modules.

## Duplicate basenames

Phase 1H-1 found 79 basename groups: 33 production groups and 47 test groups,
with `__init__.py` shared by both counts. Removing the empty duplicate
indicators MACD leaves 78 current groups and 32 production groups. SHA-256
comparison found no byte-identical non-empty tracked files.

### Phase 1H-1 production groups (33; 32 remain)

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
| `macd.py` (resolved) | `src.analysis.technical.macd` remains canonical; the empty indicators duplicate was removed |
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

Same basename does not mean redundant coverage; any post-Demo reorganization
must first compare behavior and collection identity.

## Scripts and entrypoints

| File | Classification | Finding |
| --- | --- | --- |
| `src.cli` / `alpha-pro-x` | Canonical implementation | Doctor-only supported CLI |
| `main.py` | Compatibility-only | Thin wrapper to canonical CLI |
| `scripts/bingx_vst_readiness.py` | Canonical implementation | Manual, getpass-only, read-only, directly unit tested |
| `scripts/bingx_vst_transport_diagnostic.py` | Canonical implementation | Public server-time only, directly unit tested |
| `test_exchange.py` | Confirmed dead code, removed | Obsolete live CCXT/BingX ticker script, zero consumers, outside `testpaths=["tests"]`, and no unique reusable logic |
| `src.data.main` | Compatibility-only | Import-safe factory, not a deployed command |

The root live-network script no longer exists. CI invokes neither manual VST
tool and all exchange-facing tests continue to use injected fakes.

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

## Dependency and configuration truth

`pyproject.toml` is the sole dependency/build/test/tooling authority. The
unbounded and incomplete `requirements/base.txt` and `requirements/dev.txt`
files had zero code, script, or CI consumers and were removed. CI and local
setup both install the declared `.[dev]` extra.

The declared dependencies remain unchanged in this bounded phase. In
particular, `python-dotenv` and `pydantic-settings` are retained because
`src.config.settings` configures `env_file=".env"` and is consumed by:

```text
src/exchange/bingx_websocket.py
tests/test_config.py
```

That is an exact compatibility blocker, not a readiness dependency. The
canonical Doctor and both Phase 1G VST scripts do not import
`src.config.settings`; readiness continues to collect both credentials through
`getpass` and passes them explicitly.

`orjson` and `tenacity` currently have zero direct in-repository imports. They
remain declared because removing an installed dependency changes the package
contract and is not required for the controlled Demo hardening gate. Reassess
them with external-consumer evidence after Demo.

`.env.example` is a placeholder-only compatibility template. It is the only
tracked `.env*` path.

## Secret-scanning governance

`scripts/scan_repository_secrets.py` is stdlib/Git-only and performs no
network operation. It scans:

- committed added/replaced lines for every commit after
  `vst-runtime-freeze-v1`;
- committed HEAD content and staged additions/changes;
- tracked and non-ignored working-tree content;
- forbidden credential filenames, private-key armor, known provider tokens,
  bearer credentials, credential-bearing URLs, and sensitive literal
  assignments.

It never emits the matched line or value. Findings contain only a stable rule
ID, normalized path, line, evidence source, and optional abbreviated commit.
There is no blanket test-directory bypass: only a reviewed exact set of
obviously fake test values is allowed, while private-key and live-token forms
always fail. Regression tests cover redaction, fake-value scope, commit
introduce-then-delete detection, deletion-only diffs, staged/worktree
evidence, import safety, and the current repository.

Local command:

```powershell
python scripts/scan_repository_secrets.py `
  --base-ref vst-runtime-freeze-v1
```

CI runs the same command without credentials and before pytest.

## Retained files and exact blockers

No file in the requested 24-path removal set had a blocker. The following
adjacent surfaces remain intentionally:

| Retained surface | Blocker/reason |
| --- | --- |
| 58 empty package `__init__.py` files | Removing them can change setuptools discovery, Python package identity, or pytest imports |
| Root `main.py` | Tested compatibility wrapper for `src.cli:main` |
| `src.core.kernel.bootstrap.bootstrap()` | Tested compatibility API; canonical code uses `build_runtime()` |
| `src.data.main` | Packaging/import-safety consumer |
| `src.config.settings` and dotenv dependencies | Direct consumers named in the dependency section above |
| `src.interfaces.exchange_interface` and synchronous drivers | Active driver consumers; async migration is out of scope |
| `src.domain.market_data`, `src.market.market_data`, and their consumers | Different active contracts; model consolidation is deferred |
| `src.shared.value_objects` | Public/test consumers require migration |
| Generic decision/regime/normalizer/analyzer modules | Some have consumers; broad consolidation is deferred |
| `src.domain.base`, `src.core.decision_engine`, `src.intelligence.watchlist.engine`, `src.market.normalizer`, and previously classified zero-consumer exception modules | Outside the explicitly reviewed candidate set; require a separate bounded removal manifest |

None of these retained items blocks the first controlled Demo unless later
deployment evidence proves otherwise.

## Naming audit

| Concern | Current name |
| --- | --- |
| Repository/directory | `DAlpha-Pro-Ultimate` |
| Distribution | `alpha-pro-x-infinity` |
| CLI | `alpha-pro-x` |
| Import namespace | `src` |
| Runtime display name | `Alpha Pro X Infinity` |
| Legacy settings display name | `Alpha Pro UltimateX` |

### Recommended post-controlled-Demo plan

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

Phase 1H-1 removed only the three generated artifacts recorded above. Phase
1H-2 removed exactly the 24 zero-consumer source/script paths in its reviewed
manifest and the two stale duplicate requirements files. It did not remove a
consumer-backed compatibility module or legitimate package marker.

Repository/package/CLI/import renaming, MarketData consolidation, broad
value-object migration, repository-wide Ruff/mypy cleanup, MT5,
multi-exchange, AI/ML, dashboard, and Live work are deferred until after the
first controlled Demo unless one becomes a proven operational blocker. No
trading, risk, signing, transport, readiness, execution, fill, or
reconciliation code changed.
