# Architecture

This document describes the code that is actually composed and tested at the
`vst-runtime-freeze-v1` baseline. It does not promote historical or scaffold
modules to production status.

## Runtime entry points

| Entry point | Status | Behavior |
| --- | --- | --- |
| `alpha-pro-x = src.cli:main` | Canonical installed CLI | Runs local Doctor only |
| `src.core.kernel.bootstrap.build_runtime()` | Canonical factory | Builds an unstarted, local runtime from explicit service definitions |
| `main.py` | Compatibility-only | Delegates to `src.cli.main` |
| `src.core.kernel.bootstrap.bootstrap()` | Compatibility-only | Returns an initialized `Kernel` |
| `scripts/bingx_vst_readiness.py` | Explicit manual tool | Read-only VST readiness with hidden credentials |
| `scripts/bingx_vst_transport_diagnostic.py` | Explicit manual tool | Public server-time transport diagnosis only |

`build_runtime()` does not discover, register, start, or connect exchange
services implicitly. `RuntimeMode.DOCTOR` is the only CLI mode.

## Lifecycle dependency graph

Service definitions form this graph:

```text
market-data
├── recorded-exchange-market-data-adapter
└── strategy
    └── decision
        └── execution-intent
            ├── paper-execution
            │   └── also depends directly on market-data
            └── bingx-vst
```

The exact service IDs and dependencies are:

| Service ID | Implementation | Dependencies |
| --- | --- | --- |
| `market-data` | `src.data.service.MarketDataService` | none |
| `recorded-exchange-market-data-adapter` | `src.data.adapters.recorded.RecordedExchangeMarketDataAdapter` | `market-data` |
| `strategy` | `src.strategy.service.StrategyService` | `market-data` |
| `decision` | `src.decision.recorded.DecisionService` | `strategy` |
| `execution-intent` | `src.execution_intent.service.ExecutionIntentService` | `decision` |
| `paper-execution` | `src.paper_runtime.coordinator.PaperExecutionCoordinator` | `execution-intent`, `market-data` |
| `bingx-vst` | `src.vst_runtime.coordinator.BingXVstCoordinator` | `execution-intent` |

The core service graph uses deterministic topological ordering with
registration order as its tie-breaker. Initialization and startup are
dependency-first; owned services stop in reverse order.

`RiskOrchestrator` is injected into `DecisionService`; it is not a lifecycle
service. `RecordedDecisionCoordinator` and VST readiness are also explicit
orchestration boundaries rather than graph nodes.

## Deterministic recorded pipeline

### 1. Recorded ingestion

`RecordedMarketDataPayload` is an immutable, sequence-numbered replay envelope.
The recorded adapter validates a complete batch, converts each payload to the
appropriate canonical command, and applies commands in strict sequence.

`MarketDataService` owns synchronous local snapshot, candle, and order-book
state. Its Phase 1C/1D path performs no external I/O.

### 2. Strategy and risk-gated decision

`StrategyService` invokes `MarketStructureStrategy` against the canonical
market-data service and returns a deterministic `TradeProposal`.

`DecisionService.evaluate()` validates the proposal and calls its injected,
frozen `RiskOrchestrator`. It emits a deterministic `RecordedDecision` with an
approved, rejected, or hold outcome and stable reason codes.

This is not an autonomous risk-to-order daemon. For an approved decision, the
caller must explicitly provide all of the following to
`ExecutionIntentService.construct()`:

- the matching `TradeProposal`;
- `AccountExecutionSnapshot`;
- `ApprovedRiskSnapshot`;
- `InstrumentConstraints`;
- `ExecutionPolicy`.

There is no automatic producer or runtime wiring for
`ApprovedRiskSnapshot` in this baseline.

### 3. Execution intent

`ExecutionIntentService` normalizes price and quantity to the supplied
constraints, applies the frozen execution-validation adapter, and creates a
canonical immutable intent. Hold and rejection decisions produce no-action
intents; incompatible or unsafe input produces a blocked intent.

An intent with `IntentStatus.READY` may be passed explicitly to one execution
branch. Nothing in the default runtime performs that handoff automatically.

## Paper branch

`src.paper_runtime` is the canonical Phase 1F paper runtime. It is synchronous,
in-memory, and driven by explicit calls:

1. `submit_intent()` validates and idempotently registers a ready intent.
2. `advance_market()` consumes an immutable, sequence-numbered
   `PaperMarketEvent`.
3. The coordinator applies deterministic trigger, price, quantity, fee,
   protection, account, checkpoint, and reconciliation rules.

Paper state is cleared on stop. There is no exchange network, filesystem
persistence, background thread, worker, polling loop, or automatic clock.
`src.execution.paper_trading.PaperTradingEngine` is an older low-level
compatibility surface, not the Phase 1F coordinator.

## BingX VST boundaries

### Synchronous coordinator

`BingXVstCoordinator` consumes an injected synchronous `VstTransport`. Its
frozen protocol contains execution and reconciliation operations, but no
concrete deployment transport is registered by the runtime or CLI. Therefore,
demo order submission is not an available user command at this baseline.

### Async read-only readiness

Readiness is deliberately separate from the synchronous coordinator. The
composition-only `BingXAsyncReadinessAdapter` wraps the existing
`BingXHttpClient` and exposes only:

| Adapter operation | Reused client method | HTTP operation |
| --- | --- | --- |
| `fetch_server_time()` | `get_server_time()` | `GET /openApi/swap/v2/server/time` |
| `fetch_balance()` | `get_balance()` | `GET /openApi/swap/v3/user/balance` |
| `fetch_positions()` | `get_positions()` | `GET /openApi/swap/v2/user/positions` |
| `close()` | `close()` | closes the client/session |

The public time operation runs first. Readiness collects at most three samples
on the same client/session, selects the valid sample with the lowest
round-trip time, and performs authenticated reads exactly once only after time
and drift validation succeeds. Errors are converted to stable sanitized reason
codes. The adapter does not inherit from the client and exposes no order,
cancel, amend, protection, close-position, transfer, or other mutation method.

The manual CLI validates the VST host before collecting credentials or creating
the client, prompts for both values through `getpass`, calls `asyncio.run`
exactly once at its top-level boundary, and always closes the client.
Automated tests inject async fakes and never contact BingX.

The separate public diagnostic uses the same client/session/SSL/proxy route as
production but invokes only the v2 server-time endpoint and requires no
credentials.

## Market-data contracts

Several types named `MarketData` coexist and are not interchangeable:

| Contract | Meaning | Status |
| --- | --- | --- |
| `src.data.market_data.MarketData` | Immutable top-of-book runtime snapshot with symbol, exchange, timeframe, UTC timestamp, price, bid, ask, volume, and derived spread | Canonical recorded runtime |
| `src.data.adapters.models.RecordedMarketDataPayload` | Sequence-numbered replay envelope for snapshot, candle, or order-book input with canonical JSON/digest | Canonical replay input |
| `src.data.data_manager.DataPacket` | Defensive raw OHLCV candle batch | Canonical candle storage input |
| `src.paper_runtime.models.PaperMarketEvent` | Immutable paper fill/range event with source sequence and available quantity | Canonical paper input |
| `src.exchange.models.BingX*` | Validated BingX HTTP response models | Canonical exchange boundary |
| `src.vst_runtime.models.Remote*` | VST coordinator checkpoint/reconciliation models | Canonical VST runtime |
| `src.domain.market_data.MarketData` | Alternate normalized domain model used by the older normalizer/tests | Legacy/parallel |
| `src.market.market_data.MarketData` | Alternate last-price model used by older analysis/intelligence code | Legacy/parallel |

Consumer migration is required before the two legacy models or their
normalizers can be consolidated.

## Frozen subsystem boundaries

| Tag | Canonical boundary |
| --- | --- |
| `risk-freeze-v1` | `src/risk` behavior |
| `execution-freeze-v1` | `src/execution` behavior |
| `exchange-freeze-v1` | `src/exchange` behavior |
| `data-freeze-v1` | canonical `src/data` runtime service and recorded adapter |
| `decision-freeze-v1` | canonical `src/strategy` and recorded decision/replay path |
| `execution-intent-freeze-v1` | `src/execution_intent` |
| `paper-runtime-freeze-v1` | `src/paper_runtime` |
| `vst-runtime-freeze-v1` | `src/vst_runtime`, read-only VST scripts, and reused BingX HTTP boundary |

Frozen libraries may contain public operations that are not composed into the
current runtime. Availability in a library is not deployment authorization.

## Deferred architecture

The following are intentionally not part of the operating runtime:

- VST demo-order composition and operator controls;
- shadow, micro-live, or unrestricted live operation;
- MT5 connectivity;
- production AI/ML decisioning or self-modifying weights;
- automatic multi-exchange orchestration;
- a deployed dashboard or API;
- durable runtime persistence, schedulers, background workers, or polling.

Analytics and backtesting modules exist, but they are not evidence that these
deferred deployment capabilities are complete.
