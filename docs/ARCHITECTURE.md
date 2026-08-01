# Architecture

This document describes the code that is actually composed and tested through
the manual Phase 1I-1 VST Demo canary. Frozen Phase 1G contracts remain at the
`vst-runtime-freeze-v1` baseline. Historical and scaffold modules are not
promoted to production status.

## Runtime entry points

| Entry point | Status | Behavior |
| --- | --- | --- |
| `alpha-pro-x = src.cli:main` | Canonical installed CLI | Runs local Doctor only |
| `src.core.kernel.bootstrap.build_runtime()` | Canonical factory | Builds an unstarted, local runtime from explicit service definitions |
| `main.py` | Compatibility-only | Delegates to `src.cli.main` |
| `src.core.kernel.bootstrap.bootstrap()` | Compatibility-only | Returns an initialized `Kernel` |
| `scripts/bingx_vst_readiness.py` | Explicit manual tool | Read-only VST readiness with hidden credentials |
| `scripts/bingx_vst_transport_diagnostic.py` | Explicit manual tool | Public server-time transport diagnosis only |
| `scripts/bingx_vst_demo_order.py` | Explicit manual tool | Dry-run-first, one-order VST Demo canary with two-step approval |

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
the frozen coordinator remains injection-only and unchanged.

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

### Async manual Demo canary

Phase 1I-1 adds a separate async-native composition boundary because the frozen
coordinator protocol is synchronous while the frozen `BingXHttpClient` is
async. It does not bridge, subclass, or modify either frozen contract. The
manual composition root first runs the unchanged readiness boundary, which
closes its own client. Only a `READY` result allows creation of a second client,
pinned to the VST host selected by readiness. Both clients are closed on every
path, and the script contains the sole `asyncio.run` call.

The only allowed hosts are `https://open-api-vst.bingx.com` and
`https://open-api-vst.bingx.pro`; Live hosts are rejected before credentials or
composition. With the default `.com` host, readiness preserves the frozen
network/timeout-only `.com` to `.pro` fallback. The canary client is then pinned
to readiness's actual `selected_host`, so a non-retryable write never crosses
hosts.

```text
canonical READY ExecutionIntent + supplied SHA-256
  -> current VST constraints, book, account, positions, leverage, orders
  -> immutable DemoOrderPlan + canonical digest
  -> dry-run report (default; zero writes)
  -> --execute + exact digest + typed deterministic client ID
  -> one protected non-marketable LIMIT submission
  -> query by clientOrderId
  -> cancel once if open
  -> final query + external state reconciliation
  -> canonical sanitized report
```

`BingXAsyncDemoOrderAdapter` composes the existing HTTP client and has no
generic request, market-order, transfer, withdrawal, account-setting,
cancel-all, or close-position method. Its bounded surface is:

| Category | Exact operation |
| --- | --- |
| Public reads | contract constraints and five-level order book |
| Authenticated reads | balance, same-symbol positions, leverage, open orders, recent order history, and query by deterministic `clientOrderId` |
| Authorized writes | one protected `POST .../trade/order` with `type=LIMIT`; one `DELETE .../trade/order` by `clientOrderId` if still open |
| Lifecycle | close the owned client |

The verified HTTP contracts used by that adapter are:

| Purpose | Method and path |
| --- | --- |
| Contract constraints | `GET /openApi/swap/v2/quote/contracts` |
| Five-level book | `GET /openApi/swap/v2/quote/depth` |
| Balance | `GET /openApi/swap/v3/user/balance` |
| Positions | `GET /openApi/swap/v2/user/positions` |
| Current leverage | `GET /openApi/swap/v2/trade/leverage` |
| Position mode | `GET /openApi/swap/v1/positionSide/dual` |
| Existing/open history | `GET /openApi/swap/v2/trade/openOrders` and `GET /openApi/swap/v2/trade/allOrders` |
| Submit/query/cancel | `POST`, `GET`, and `DELETE /openApi/swap/v2/trade/order`; query and cancel use `clientOrderId` |

Attached `stopLoss` and `takeProfit` parameters are compact JSON objects with
`STOP_MARKET`/`TAKE_PROFIT_MARKET`, explicit `MARK_PRICE`, trigger price, and
`stopGuaranteed=false`. They are not the scalar values accepted by an older
client convenience method. The adapter invokes the existing generic request
boundary so URL construction, signing order, headers, timeouts, response/error
handling, and non-retryable write behavior stay owned by `BingXHttpClient`.

The client ID retains the frozen coordinator's `bingx-vst:<intent_id>` SHA-256
seed and 24-hex suffix. The manual boundary removes the frozen helper's hyphen
from the prefix because current official validation guidance conflicts on
punctuation and the fail-closed compatible subset is lowercase alphanumeric,
at most 40 characters. The frozen synchronous helper is not modified.

Current precision fields are converted to `10^-pricePrecision` and
`10^-quantityPrecision`; this is an explicit inference because the official
contract schema provides precision counts but no separate tick/step fields.
An approved intent must already be exactly normalized to those current values;
the canary blocks instead of silently changing an approved order. Minimum
quantity/notional, a fixed 10-VST-equivalent notional ceiling, current leverage
at or below 2, an empty same-symbol position, a non-marketable limit, both
attached protections, and duplicate-order checks are mandatory.

Two narrowly proven transport defects required reopening the frozen HTTP
client. `get_positions()` now rejects a successful payload that omits `data`
instead of fabricating an authoritative empty position list. Retryable HTTP
responses such as rate limits and 5xx unavailability now retry on the same host;
only a network/timeout failure advances `.com` to `.pro`, as required by the
official host contract. Valid empty position arrays and all endpoint, signing,
timeout, and model contracts are unchanged. The canary adapter likewise
requires the documented `data` container for open-order and order-history
reads.

Submission and cancellation are non-retryable writes. A submit transport
failure or post-dispatch response-schema failure is treated as ambiguous and
followed only by a client-ID query. A final client-ID absence check plus fresh
constraint, book, same-symbol position, leverage, position-mode, and open-entry
validations immediately precede submission. Any existing same-symbol
non-reduce-only open order blocks the plan. An unexpected partial/full fill or
unresolved remote state
activates the canonical report's `KillSwitchState`; there is no recovery order
or automatic flatten. Reports contain plan/order identifiers and small
reconciliation summaries, but no credentials, signatures, headers, signed
queries, raw response bodies, or account totals. No report persistence layer
was added.

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

- unattended VST Demo execution or automatic recovery;
- shadow, micro-live, or unrestricted live operation;
- MT5 connectivity;
- production AI/ML decisioning or self-modifying weights;
- automatic multi-exchange orchestration;
- a deployed dashboard or API;
- durable runtime persistence, schedulers, background workers, or polling.

Analytics and backtesting modules exist, but they are not evidence that these
deferred deployment capabilities are complete.
