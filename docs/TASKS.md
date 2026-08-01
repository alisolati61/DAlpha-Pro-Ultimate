# Tasks

This file tracks work that remains after the frozen Phase 1G baseline. It must
not be used to bypass subsystem freeze rules.

## Phase 1H-1

- [x] Replace the empty/stale top-level documentation with repository truth.
- [x] Document canonical runtime entry points and service dependencies.
- [x] Distinguish all market-data contracts.
- [x] Inventory empty files, `_old.py` files, duplicate basenames, obsolete
  scripts, generated artifacts, and root temporary files.
- [x] Document compatibility-only and consumer-migration boundaries.
- [x] Add placeholder-only `.env.example` guidance.
- [x] Expand ignore rules for credentials, caches, build/coverage/editor
  output, readiness output, and local databases.
- [x] Add a credential-free GitHub Actions baseline.
- [x] Keep Phase 1G readiness getpass-only and automated VST tests fake-only.
- [x] Record naming and license decisions without renaming or licensing here.

## Phase 1H-2 - Bounded cleanup and governance

- [x] Prove zero static imports, dynamic imports, runtime/CLI references,
  documentation contracts, and test dependencies for every removal candidate.
- [x] Remove the four reviewed `_old.py` modules.
- [x] Remove the 15 reviewed empty feature scaffolds, the misnamed
  `exchange/connectors/init.py`, and three extensionless exchange scaffolds.
- [x] Delete root `test_exchange.py`; its only behavior was an obsolete,
  zero-consumer real-network CCXT ticker call.
- [x] Add import/path regression coverage for the complete removal manifest.
- [x] Add a deterministic, value-redacting, stdlib/Git secret scanner to CI.
- [x] Cover tracked/staged/worktree content and per-commit additions after
  `vst-runtime-freeze-v1`.
- [x] Restrict fake credential allowances to a reviewed exact test-only set.
- [x] Retire zero-consumer `requirements/base.txt` and
  `requirements/dev.txt`; `pyproject.toml` is the sole dependency authority.
- [x] Preserve the getpass-only Phase 1G readiness boundary.
- [x] Record every retained compatibility blocker and post-Demo deferral.

## Phase 1I-1 - Controlled BingX VST Demo canary

- [x] Add a separate async-native, manual-only canary without modifying the
  frozen synchronous VST coordinator or readiness behavior.
- [x] Accept only the exact canonical serialized `READY` `ExecutionIntent` and
  its supplied SHA-256; reject stale, noncanonical, non-ready, or modified
  input before composition.
- [x] Build an immutable canonical `DemoOrderPlan` from current contract,
  order-book, balance, positions, leverage, open-order, and order-history
  reads; bind all approved order fields and prerequisite snapshot digests.
- [x] Enforce VST-only hosts, `LIMIT`/`GTC`, non-marketability, current
  precision/minimums, both protections, fixed 10-notional and 2x-leverage
  ceilings, no same-symbol position, and duplicate canary rejection.
- [x] Require `--execute`, the exact rebuilt plan digest, and exact typed
  `SUBMIT <clientOrderId>` approval before the only submission call.
- [x] Recheck deterministic client-ID absence, constraints, book
  non-marketability, same-symbol positions, leverage, position mode, and open
  entry orders after confirmation immediately before that submission.
- [x] Submit at most once with automatic write retry disabled; query and cancel
  by deterministic client ID, then query and externally reconcile final state.
- [x] Fail closed on ambiguous submission/cancellation or unexpected fill;
  never resubmit blindly or auto-flatten.
- [x] Keep credentials getpass-only and outputs canonical, minimal, and free of
  credentials, signatures, signed queries, headers, raw bodies, paths, and
  account totals.
- [x] Keep automated tests fake-only and enforce closure, import safety, narrow
  transport reachability, and exactly one CLI-boundary `asyncio.run`.
- [ ] Before a human runs the canary, issue/verify least-privilege VST-only
  credentials, name the operator and incident owner, preconfigure leverage at
  or below the fixed cap, and approve sanitized report retention.
- [ ] After any `AMBIGUOUS` or `UNEXPECTED_FILL` result, reconcile the VST
  account manually before another invocation; no frozen automatic recovery
  contract exists.

## Phase 1I-2 - Controlled VST intent preparation

- [x] Add one explicit offline composition root over the frozen recorded
  adapter, market-data, strategy, decision, risk, and execution-intent services.
- [x] Require exactly four already-canonical compact JSON inputs: recorded
  market events, account/portfolio/risk state, instrument constraints, and
  execution/risk policy; verify every separately supplied source SHA-256 and
  reject undeclared fields and credential-bearing keys.
- [x] Require fresh account and constraint observations and a fresh latest
  candle under the existing intent freshness and future-tolerance bounds.
- [x] Restrict the first canonical preparation boundary to the reviewed
  `BTC-USDT` canary symbol and reject all other symbols.
- [x] Rehydrate explicit account kill-switch and circuit-breaker state locally,
  capture exactly one frozen risk evaluation, and derive approved-risk input
  only after that evaluation returns `APPROVED`.
- [x] Bind exact source-document digests, frozen proposal/decision IDs, the
  exact risk call/result digest, and the final canonical intent digest.
- [x] Require risk evaluation at the fixed worst admitted `2x` leverage and
  block normalized entry notional above the fixed `10` canary ceiling.
- [x] Create `.operator-artifacts/<intent_id>.json` exclusively only for
  `READY`; keep blocked/no-action reports free of artifact paths and digests and
  ignore all local operator artifacts in Git.
- [x] Keep preparation free of credentials, environment/dotenv loading,
  network calls, exchange reads, and every order/cancel/write operation.
- [x] Hand a reviewed artifact and digest only to the separate Phase 1I-1 dry
  run, then stop before `--execute`, typed approval, or submission.
- [x] Add a separate Phase 1I-3 read-only acquisition path for fresh BingX
  market/account/constraint facts and a fixed policy; canonical hashes alone
  still do not attest directly supplied Phase 1I-2 input.
- [ ] Define a separately approved shared/durable risk-state checkpoint before
  any unattended or multi-process composition; Phase 1I-2 intentionally has no
  automatic shared risk-state persistence.

## Phase 1I-3 - Attested read-only canary capture and dry-run rehearsal

- [x] Add a separate manual VST-only CLI that rejects production hosts before
  hidden credential prompts and runs existing readiness before every other
  read.
- [x] Reuse the frozen `BingXHttpClient` signing, headers, timeout, URL,
  fallback, response, and error path behind a composition-only adapter exposing
  candle, book, strict balance, position, contract, leverage, mode, open-order,
  income, selected-host, and close operations only.
- [x] Validate complete, unique, consecutive, fresh `BTC-USDT` one-minute
  candles and bind the current validated top of book without changing the
  frozen candle-only preparation schema.
- [x] Derive balance, equity, available/used margin, position exposure,
  conservative UTC-day gross loss, consecutive realized losses, and zero
  portfolio risk only from complete authoritative reads; fail on absent or
  saturated facts instead of inventing values.
- [x] Block active positions, open same-symbol entry orders, unexplained used
  margin, unsafe leverage, invalid position mode, disabled/incompatible
  contracts, stale data, production/Live identity, and every account mutation.
- [x] Generate the deterministic versioned policy internally with fixed
  `BTC-USDT`, protected `LIMIT`, `10` quote-notional, `2x` leverage,
  no-pyramiding, no-position, and five-minute-TTL requirements; expose no CLI
  policy override.
- [x] Write four canonical files and a source-attestation manifest exclusively
  under `.operator-artifacts/canary-inputs/<capture_id>/`, with no overwrite,
  symlink/path escape, residual temporary file, credential, or console balance.
- [x] Print exact preparation and dry-run-without-`--execute` handoff commands;
  do not invoke either command automatically and stop after `DRY_RUN_READY`.
- [x] Keep automated capture/preparation/Demo rehearsal fake-only and prove
  lifecycle closure, import safety, deterministic bytes/digests, narrow reads,
  and zero exchange write reachability.
- [ ] Add an approved durable local risk-state authority before treating a
  standalone fresh capture's inactive kill-switch state as valid across
  processes or prior operator sessions.

## Pre-existing quality debt

These failures predate Phase 1H-1 and are not suppressed with repository-wide
ignore rules:

- [ ] Resolve 130 repository-wide Ruff findings. The post-exchange-freeze
  Python surface is clean and forms the initial CI Ruff baseline.
- [ ] Resolve 32 repository-wide mypy errors in 15 files. The canonical
  runtime/frozen subsystem scope succeeds with
  `--follow-imports=skip --ignore-missing-imports` and forms the initial CI
  mypy baseline.
- [ ] Expand both CI static gates to all Python files after the findings are
  fixed; do not make them non-blocking and do not add blanket exclusions.
- [x] Remove the unbounded duplicate requirements lists and retain
  authoritative `pyproject.toml`.
- [ ] Remove import-time dotenv settings from supported code or formally
  retain them as a compatibility contract. Current VST readiness is not a
  consumer.
- [ ] Reassess zero-direct-import `orjson` and `tenacity` declarations with
  external-consumer evidence after controlled Demo.
- [x] Remove root `test_exchange.py` after proving zero consumers and duplicate
  fake-based coverage for its non-unique behavior.

The exact file inventory and classifications are in
[REPOSITORY_AUDIT.md](REPOSITORY_AUDIT.md).

<details>
<summary>Exact repository-wide static-analysis debt at the 1H-1 audit</summary>

Full Ruff totals are `I001=71`, `F401=43`, `E501=5`, `E731=5`, `F841=2`,
`B009=1`, `B011=1`, `B905=1`, and `E712=1` (130 findings in 83 files):

```text
src/adapters/base_adapter.py                                      I001:1
src/ai/weight_optimizer.py                                       F401:1
src/analysis/ict/break_of_structure.py                           F841:1
src/analysis/ict/fair_value_gap.py                               F841:1 I001:1
src/analysis/smart_money/__init__.py                             I001:1
src/analysis/smart_money/choch.py                                I001:1
src/analysis/technical/fibonacci.py                              I001:1
src/analysis/technical/swing.py                                  I001:1
src/analysis/technical/volume_profile.py                         B905:1
src/backtesting/__init__.py                                      I001:1
src/backtesting/trade_simulator.py                               I001:1
src/core/asset_scorer.py                                         I001:1
src/core/context/__init__.py                                     I001:1
src/core/context/context_builder.py                              I001:1
src/core/contracts/__init__.py                                   I001:1
src/core/contracts/configuration.py                              I001:1
src/core/contracts/registry.py                                   I001:1
src/core/decision_engine.py                                      F401:1 I001:1
src/core/dependency_injection/__init__.py                        I001:1
src/core/dependency_injection/container.py                       I001:1
src/core/dependency_injection/provider.py                        I001:1
src/core/event_bus/subscription.py                               F401:1
src/core/exceptions/__init__.py                                  I001:1
src/core/strategy_selector.py                                    I001:1
src/core/types/__init__.py                                       I001:1
src/decision/decision_engine.py                                  I001:1
src/domain/entities/__init__.py                                  I001:1
src/domain/value_objects/__init__.py                             I001:1
src/domain/value_objects/market.py                               I001:1
src/domain/value_objects/money.py                                I001:1
src/domain/value_objects/price.py                                I001:1
src/domain/value_objects/symbol.py                               I001:1
src/exchange/__init__.py                                        F401:35
src/exchange/bingx_websocket.py                                  E501:5 E712:1 F401:3
src/intelligence/analyzers/technical_score_analyzer.py           I001:1
src/logger/__init__.py                                           F401:1
src/logger/logger.py                                             I001:1
src/risk/__init__.py                                             I001:1
src/shared/clock/__init__.py                                     I001:1
src/shared/clock/clock.py                                        I001:1
src/shared/ids/__init__.py                                       I001:1
src/shared/mapper/registry.py                                    F401:1
src/shared/result/__init__.py                                    I001:1
src/shared/serializer/__init__.py                                I001:1
src/shared/serializer/json_serializer.py                         I001:1
src/shared/validators/__init__.py                                I001:1
src/shared/value_objects/__init__.py                             I001:1
src/shared/value_objects/money.py                                I001:1
src/shared/value_objects/percentage.py                           I001:1
tests/core/context/test_core_context.py                          I001:1
tests/core/dependency_injection/test_container.py                I001:1
tests/core/exceptions/test_exceptions.py                         I001:1
tests/core/registry/test_core_registry.py                        I001:1
tests/core/types/test_core_types.py                              I001:1
tests/domain/value_objects/test_domain_symbol.py                 I001:1
tests/domain/value_objects/test_market.py                        I001:1
tests/shared/clock/test_clock.py                                 I001:1
tests/shared/ids/test_ids.py                                     I001:1
tests/shared/mapper/test_mapper.py                               I001:1
tests/shared/result/test_shared_result.py                        I001:1
tests/shared/value_objects/test_value_objects.py                 I001:1
tests/test_backtesting_exports.py                                I001:1
tests/test_base_exchange.py                                      I001:1
tests/test_event_bus.py                                          B011:1 I001:1
tests/test_execution_engine.py                                   I001:1
tests/test_execution_exports.py                                  I001:1
tests/test_execution_history.py                                  I001:1
tests/test_execution_report.py                                   I001:1
tests/test_monte_carlo.py                                        I001:1
tests/test_order_tracker.py                                      I001:1
tests/test_paper_trading.py                                      I001:1
tests/test_portfolio_sync.py                                     I001:1
tests/test_position_manager.py                                   I001:1
tests/test_position_sizer.py                                     I001:1
tests/test_risk_exports.py                                       I001:1
tests/test_rsi_analyzer.py                                       I001:1
tests/test_smart_money_exports.py                                I001:1
tests/test_smart_router.py                                       E731:2
tests/test_strategy_selector.py                                  I001:1
tests/unit/exchange/test_exchange_exports.py                     B009:1
tests/unit/exchange/test_exchange_factory.py                     E731:2
tests/unit/execution/test_smart_router.py                         E731:1
tests/unit/risk/test_position_sizer.py                            I001:1
```

Full mypy totals are `arg-type=15`, `call-overload=5`, `assignment=4`,
`misc=3`, `return-value=2`, `union-attr=2`, and `var-annotated=1` (32
errors in 15 files):

```text
src/analysis/derivatives/long_short_ratio.py               assignment:1
src/analysis/derivatives/open_interest.py                   assignment:1
src/analysis/onchain/holder_profit.py                       assignment:1
src/analysis/orderflow/imbalance.py                         assignment:1
src/analysis/smart_money/market_structure.py                call-overload:1 var-annotated:1
src/analysis/technical/atr.py                               union-attr:1
src/analysis/technical/ema.py                               union-attr:1
src/backtesting/backtest_engine.py                          call-overload:1
src/backtesting/monte_carlo.py                              call-overload:1
src/backtesting/statistics_engine.py                        call-overload:1
src/backtesting/strategy_runner.py                          call-overload:1
src/exchange/bingx_client.py                                arg-type:11
src/exchange/websocket.py                                   misc:3
src/intelligence/analyzers/technical_score_analyzer.py      arg-type:4
src/shared/result/result.py                                 return-value:2
```

</details>

## Deferred until after controlled Demo

The following broad migrations do not block the first controlled Demo and were
explicitly excluded from Phase 1H-2. Reopen one only for a proven operational
blocker or as a separately approved post-Demo phase.

### Naming

- [ ] Approve one product identity.
- [ ] Plan an atomic migration for repository name, distribution,
  `alpha-pro-x` command, runtime display name, and the `src` import namespace.
- [ ] Provide compatibility shims and deprecation tests for any public surface
  that cannot migrate atomically.

### Contract migration

- [ ] Inventory external as well as in-repository consumers before removal.
- [ ] Migrate `src.domain.market_data.MarketData` and
  `src.market.market_data.MarketData` consumers to an approved canonical
  contract or explicit adapters.
- [ ] Consolidate domain/shared money, price, quantity, and symbol values only
  after public/test consumers move.
- [ ] Decide ownership for parallel decision/regime/normalizer/analyzer APIs.
- [ ] Replace legacy synchronous exchange interfaces/drivers only after their
  consumers have an async-native migration.

### Removal

- [ ] Keep legitimate empty `__init__.py` package markers unless packaging and
  pytest import behavior are proven unchanged.
- [ ] Review any additional zero-consumer candidates under a new bounded
  manifest; this phase grants no general cleanup authority.

### Security and governance

- [ ] Select a license after ownership, distribution intent, and third-party
  obligations are reviewed. No license is granted by the current repository.
- [x] Add deterministic secret scanning to CI with a reviewed fake-only
  test-value allowlist and value-redacting output.
- [ ] Complete operational credential rotation, least-privilege VST policy,
  operator identity, and incident ownership before the first manual canary run.
- [ ] Decide artifact-retention policy for sanitized diagnostics and
  checkpoints.

## Deferred deployment work

- [x] Add the separately authorized, manual-only Phase 1I-1 VST Demo canary.
- [ ] Add shadow operation with zero order submission.
- [ ] Gate micro-live operation behind independent security, risk, legal, and
  operational approval.
- [ ] Evaluate MT5, production AI/ML, multi-exchange orchestration, dashboard,
  and persistence only as separately scoped future phases.

Repository/package/CLI/import namespace renaming, MarketData consolidation,
broad value-object migration, full Ruff cleanup, and full mypy cleanup remain
deferred until after controlled Demo unless they become operational blockers.
None of the deployment items above is authorized by Phase 1H-2.
