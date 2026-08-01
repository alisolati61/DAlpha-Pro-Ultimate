# Project Manifest

This manifest is the status index for the repository through the bounded
manual Phase 1I-2 intent-preparation and Phase 1I-1 Demo canary boundaries.
Phase 1G runtime/readiness contracts remain frozen at `vst-runtime-freeze-v1`;
Phase 1I-1 narrowly hardened missing-position data rejection and corrected host
advancement so only network/timeout failures move `.com` reads to `.pro`.
Architecture details live in
[ARCHITECTURE.md](ARCHITECTURE.md); file-level legacy findings live in
[REPOSITORY_AUDIT.md](REPOSITORY_AUDIT.md).

## Identity

| Surface | Current value | Authority |
| --- | --- | --- |
| Repository/directory | `DAlpha-Pro-Ultimate` | repository hosting/path |
| Distribution | `alpha-pro-x-infinity` | `pyproject.toml` |
| CLI | `alpha-pro-x` | `[project.scripts]` |
| Python imports | `src.*` | packaged namespace |
| Runtime display name | `Alpha Pro X Infinity` | core runtime configuration |
| Supported Python | `>=3.12` | `pyproject.toml` |

These names are inconsistent. They remain unchanged through Phase 1H-2; the
coordinated migration is deferred until after controlled Demo execution unless
it becomes an operational blocker.

## Status legend

- **Frozen:** implemented, tested, tagged, and change-controlled.
- **Canonical:** current supported path, whether or not separately tagged.
- **Compatibility-only:** retained for existing imports/tests; not the current
  operating path.
- **Scaffold/deferred:** not an implemented runtime capability.

## Completed and frozen boundaries

| Boundary | Tag | Commit | Status |
| --- | --- | --- | --- |
| Risk | `risk-freeze-v1` | `61c5b85` | Frozen |
| Execution | `execution-freeze-v1` | `2549805` | Frozen |
| Exchange | `exchange-freeze-v1` | `01a259c` | Frozen |
| Canonical data/replay | `data-freeze-v1` | `ba6a443` | Frozen |
| Recorded strategy/decision | `decision-freeze-v1` | `29c247d` | Frozen |
| Execution intent | `execution-intent-freeze-v1` | `c33809f` | Frozen |
| Paper runtime | `paper-runtime-freeze-v1` | `aa29cbe` | Frozen |
| VST runtime/readiness | `vst-runtime-freeze-v1` | `610ec0e` | Frozen |

## Canonical module map

| Area | Canonical modules | Implemented responsibility |
| --- | --- | --- |
| Packaging/CLI | `pyproject.toml`, `src.cli` | Installable package and Doctor-only CLI |
| Runtime configuration | `src.core.config` | Explicit defaults/TOML/override loading without automatic service registration |
| Runtime kernel | `src.core.context`, `src.core.event_bus`, `src.core.kernel`, `src.core.lifecycle`, `src.core.services` | Local lifecycle, service graph, and composition |
| Diagnostics | `src.core.diagnostics` | Import-safe local Doctor report |
| Market data | `src.data.market_data`, `src.data.service` | Immutable snapshot and transactional in-memory state |
| Recorded replay | `src.data.adapters` | Validated sequence-controlled recorded ingestion |
| Strategy | `src.strategy.market_structure`, `src.strategy.models`, `src.strategy.service` | Deterministic market-structure proposal |
| Decision | `src.decision.recorded`, `src.decision.replay` | Risk-gated recorded decisions and explicit coordination |
| Risk | `src.risk` | Frozen risk checks/orchestration |
| Execution library | `src.execution` | Frozen request validation and execution primitives |
| Execution intent | `src.execution_intent` | Deterministic constraint-aware intent construction |
| Paper runtime | `src.paper_runtime` | Deterministic in-memory fills, ledger, checkpoints, and reconciliation |
| Exchange library | `src.exchange` | Frozen exchange contracts, BingX/CCXT clients, response/error normalization |
| VST runtime | `src.vst_runtime` | Protocol-driven synchronous VST coordinator and reconciliation |
| VST readiness | `src.vst_runtime.readiness`, `scripts/bingx_vst_readiness.py` | Async read-only server-time, balance, and positions validation |
| Public VST diagnosis | `scripts/bingx_vst_transport_diagnostic.py` | Credential-free server-time transport classification |
| Manual intent preparation | `src.vst_runtime.intent_preparation`, `scripts/bingx_vst_prepare_intent.py` | Offline four-input composition through frozen strategy/decision/risk/intent gates to a `READY`-only ignored artifact |
| Manual VST Demo canary | `src.vst_runtime.demo_order`, `src.vst_runtime.demo_transport`, `scripts/bingx_vst_demo_order.py` | Canonical dry-run plan and exactly gated one-order submit/query/cancel/reconcile lifecycle |
| Repository security | `scripts/scan_repository_secrets.py` | Deterministic value-redacting scan of committed and current repository content |

The exchange and execution libraries are real, tested libraries. They are not
automatically composed into the installed CLI or default runtime.

## Canonical data and execution flow

```text
RecordedMarketDataPayload
  -> recorded adapter
  -> canonical MarketDataService
  -> deterministic TradeProposal
  -> risk-gated RecordedDecision
  -> explicit account + approved-risk + constraints + policy
  -> ExecutionIntent
  -> paper coordinator OR explicitly injected VST coordinator
                     OR Phase 1I-2 READY-only local artifact
                        -> Phase 1I-1 manual async VST Demo dry run
```

There is no default-runtime risk-snapshot producer and no automatic
paper-to-VST switch. Phase 1I-2 can derive an approved-risk snapshot only after
one explicit frozen risk evaluation over four operator-supplied canonical
documents. A caller must still supply and compose each boundary explicitly.
The account/risk-state and constraint documents are not exchange-attested, and
there is no automatic shared or durable risk-state checkpoint.

## Compatibility and parallel surfaces

| Surface | Status |
| --- | --- |
| Root `main.py` | Compatibility wrapper for `src.cli.main` |
| `src.core.kernel.bootstrap.bootstrap()` | Compatibility helper; canonical composition uses `build_runtime()` |
| `src.data.main` | Import-safe data-service factory retained for compatibility |
| `src.execution_intent.validation` | Explicit adapter to the frozen execution validator |
| `src.execution.paper_trading.PaperTradingEngine` | Older low-level paper API; not the Phase 1F runtime |
| `src.domain.market_data` and `src.market.market_data` | Actively consumed legacy data contracts requiring migration |
| `src.shared.value_objects` | Test/public compatibility values parallel to domain values |
| Generic/AI decision and regime engines | Parallel legacy/deferred surfaces; not the frozen recorded path |
| `src.config.settings` | Legacy environment/dotenv settings; not used by Doctor or VST readiness |
| Removed `requirements/*.txt` | Zero-consumer duplicate metadata retired in Phase 1H-2; `pyproject.toml` is the sole authority |

No compatibility module is silently aliased to a canonical contract.

## Implemented safety properties

- deterministic recorded replay and canonical serialization;
- fail-closed risk and execution-intent validation;
- explicit lifecycle/service dependencies;
- local, deterministic, network-free paper execution;
- VST configuration limits, reconciliation, checkpoints, and kill-switch state;
- read-only BingX VST readiness with bounded clock sampling;
- sanitized transport diagnostics and deterministic host fallback;
- fake-only automated VST tests;
- offline, credential-free Phase 1I-2 preparation with strict canonical
  market/account/constraint/policy schemas, supplied source-digest verification,
  freshness checks, source and risk provenance digests, fixed `2x` risk
  evaluation and `10`-notional ceiling, and exclusive `READY`-only artifact
  creation;
- dry-run-first manual VST Demo canary with exact intent/plan digests, current
  constraints/account reads, a narrow adapter, one non-retryable protected
  limit submission, deterministic client-ID recovery, and fail-closed final
  reconciliation;
- Doctor-only installed CLI and no automatic exchange wiring;
- deterministic secret scanning with no runtime network or credential output;
- removal regression coverage for the complete bounded dead-code manifest.

## Not implemented or not deployment-ready

- automatic, unattended, or default-runtime VST Demo submission;
- exchange-attested acquisition/currentness for Phase 1I-2 account,
  risk-state, and instrument-constraint inputs;
- automatic shared/durable risk-state checkpointing across preparation runs;
- shadow-mode orchestration;
- micro-live or unrestricted live operation;
- MT5;
- production AI/ML decisioning;
- automatic multi-exchange routing/orchestration;
- a deployed dashboard/API;
- durable paper/VST storage;
- schedulers, background workers, or polling runtime;
- a resolved open-source/commercial license.

Files bearing related names may exist as libraries or scaffolds; that does not
change these statuses.

## Phase 1H-2 repository disposition

- Removed four unreferenced `_old.py` AI modules.
- Removed 19 zero-byte unsupported/misnamed/extensionless scaffolds.
- Removed the zero-consumer root live-network ticker script.
- Retired two incomplete duplicate requirements files.
- Retained all legitimate package markers and consumer-backed compatibility
  modules.
- Retained legacy dotenv settings because
  `src.exchange.bingx_websocket` and `tests/test_config.py` consume them;
  Doctor and VST readiness remain non-consumers.
- Deferred naming, MarketData/value-object consolidation, and full Ruff/mypy
  cleanup until after controlled Demo unless operationally blocking.

## Source-of-truth order

When documents or older modules disagree, use this order:

1. frozen tests and contracts at the tag named for the subsystem;
2. current canonical code and `pyproject.toml`;
3. this manifest and `ARCHITECTURE.md`;
4. compatibility modules;
5. unsupported scaffolds and historical audit artifacts.
