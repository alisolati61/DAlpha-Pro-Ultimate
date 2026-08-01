# Alpha Pro X Infinity

Alpha Pro X Infinity is a Python 3.12 trading-system foundation focused on
deterministic, fail-closed decision and execution boundaries. The repository
currently supports local recorded-market replay, deterministic strategy and
risk decisions, canonical execution-intent construction, in-memory paper
execution, and an explicit read-only BingX VST readiness check.

Phase 1I-2 provides a separate offline, manual preparation step that converts
four explicit canonical inputs into a `READY` execution-intent artifact only
after the frozen strategy, decision, risk, and intent gates approve it. Phase
1I-1 provides the separate two-step BingX VST Demo canary. It accepts only a
canonical `READY` execution intent, defaults to a read-only dry run, and can
submit at most one protected non-marketable limit order after exact digest and
typed client-ID approval. Neither tool is registered in the installed CLI or
default runtime.

It is not a live-trading application. No default runtime submits an order, and
the installed CLI exposes local diagnostics only.

## Current architecture

The implemented recorded-data path is:

```text
RecordedMarketDataPayload
  -> RecordedExchangeMarketDataAdapter
  -> MarketDataService
  -> StrategyService / MarketStructureStrategy
  -> DecisionService + injected frozen RiskOrchestrator
  -> explicit account / approved-risk / constraint / policy inputs
  -> ExecutionIntentService
  -> PaperExecutionCoordinator OR injected BingXVstCoordinator
                          OR manual offline intent preparation
                             -> manual DemoOrderPlan canary
```

The canonical runtime factory,
`src.core.kernel.bootstrap.build_runtime`, returns an unstarted, local runtime.
Services must be supplied explicitly; exchange and execution services are not
registered automatically. The installed `alpha-pro-x` command runs only the
safe local Doctor.

The service dependency graph is deterministic:

```text
market-data
├── recorded-exchange-market-data-adapter
└── strategy
    └── decision
        └── execution-intent
            ├── paper-execution  (also depends on market-data)
            └── bingx-vst
```

Risk is an injected collaborator of `DecisionService`, not a lifecycle graph
node. See [Architecture](docs/ARCHITECTURE.md) and the
[Project Manifest](docs/PROJECT_MANIFEST.md) for the precise boundaries.

## Frozen milestones

The following Git tags identify reviewed subsystem contracts:

| Tag | Boundary |
| --- | --- |
| `risk-freeze-v1` | Risk management |
| `execution-freeze-v1` | Execution library |
| `exchange-freeze-v1` | Exchange library and BingX client |
| `data-freeze-v1` | Canonical local market data and recorded adapter |
| `decision-freeze-v1` | Recorded strategy/decision path |
| `execution-intent-freeze-v1` | Canonical execution intent |
| `paper-runtime-freeze-v1` | Deterministic paper runtime |
| `vst-runtime-freeze-v1` | BingX VST runtime and read-only readiness |

Frozen means changes require a proven defect or an explicitly approved later
phase. It does not mean that every historical module in the repository is part
of the canonical runtime.

## Determinism and execution safety

- Recorded inputs are immutable, sequence-checked, and canonically serialized.
- Decisions, execution intents, reports, and checkpoints use deterministic
  identifiers or digests.
- Risk rejection, invalid contracts, and ambiguous remote state fail closed.
- Paper execution is synchronous and in memory. It uses explicit market
  advancement, deterministic fills, reconciliation, and no network access.
- The VST coordinator is protocol-driven and is not registered by the default
  runtime or CLI.
- VST readiness is a separate async, read-only boundary. It can reach only
  server time, account balance, and positions, then closes its client.

## Installation

Create an isolated environment from the repository root:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

On POSIX shells, activate with `source .venv/bin/activate`. `pyproject.toml` is
the sole dependency and tooling authority. The stale duplicate requirements
files were retired in Phase 1H-2; CI and local setup both install `.[dev]`.

Run the local Doctor:

```powershell
alpha-pro-x doctor
```

Running `alpha-pro-x` without a subcommand is equivalent. The root `main.py`
entry point remains a compatibility wrapper:

```powershell
python main.py
```

## BingX VST read-only readiness

This command is manual and intentionally excluded from automated tests and CI:

```powershell
python scripts/bingx_vst_readiness.py `
  --host https://open-api-vst.bingx.com
```

Both the VST API key and secret are requested with `getpass`; there are no
credential command-line flags and this command does not load `.env`. The host
must be an allowlisted VST host before the client is created. The operation
order is bounded public server-time sampling, one balance read, then one
positions read. If time validation fails, authenticated reads do not run.
No order, cancel, amend, transfer, or other write operation is exposed by the
readiness adapter.

For public transport diagnosis without credentials:

```powershell
python scripts/bingx_vst_transport_diagnostic.py `
  --host https://open-api-vst.bingx.com
```

That command uses the production BingX HTTP/session path but calls only the
public server-time endpoint. Do not run either command as part of the automated
quality gates.

## Offline VST intent preparation

Phase 1I-2 is an explicit, credential-free composition root. From the repository
root, provide four placeholder-named local files; do not put credentials or
other secrets in them:

```powershell
(Get-FileHash -Algorithm SHA256 "<CANONICAL_MARKET_INPUT.json>").Hash.ToLowerInvariant()
(Get-FileHash -Algorithm SHA256 "<CANONICAL_ACCOUNT_INPUT.json>").Hash.ToLowerInvariant()
(Get-FileHash -Algorithm SHA256 "<CANONICAL_CONSTRAINTS_INPUT.json>").Hash.ToLowerInvariant()
(Get-FileHash -Algorithm SHA256 "<CANONICAL_POLICY_INPUT.json>").Hash.ToLowerInvariant()
```

```powershell
python scripts/bingx_vst_prepare_intent.py `
  --market-input "<CANONICAL_MARKET_INPUT.json>" `
  --market-digest "<MARKET_INPUT_SHA256>" `
  --account-input "<CANONICAL_ACCOUNT_INPUT.json>" `
  --account-digest "<ACCOUNT_INPUT_SHA256>" `
  --constraints-input "<CANONICAL_CONSTRAINTS_INPUT.json>" `
  --constraints-digest "<CONSTRAINTS_INPUT_SHA256>" `
  --policy-input "<CANONICAL_POLICY_INPUT.json>" `
  --policy-digest "<POLICY_INPUT_SHA256>"
```

Each file must already be UTF-8 canonical compact JSON: object keys sorted,
no insignificant whitespace, finite values only, and no undeclared fields. The
four exact top-level schemas are:

- `bingx-vst-recorded-market-v1`: `schema_version`, `exchange`, `symbol`,
  `timeframe`, and nonempty sequence-ordered `events`; every event has exactly
  `kind`, `payload`, and `sequence`, every `kind` is `candles`, and all candle
  payload identities and strictly increasing UTC-`Z` timestamps must match the
  outer symbol/timeframe; Phase 1I-2 is intentionally restricted to
  `BTC-USDT`;
- `bingx-vst-account-v1`: `schema_version`, `observed_at`, `equity`,
  `available_balance`, `current_exposure`, `open_position_quantity`,
  `portfolio`, and `risk_state`; `portfolio` contains exactly `balance`,
  `equity`, `used_margin`, `daily_loss`, `total_risk`, and `open_positions`,
  while `risk_state` contains exactly `kill_switch_active` and
  `circuit_breaker_consecutive_losses`;
- `bingx-vst-constraints-v1`: `schema_version`, `exchange`, `symbol`,
  `observed_at`, `price_tick`, `quantity_step`, `minimum_quantity`,
  `minimum_notional`, and nullable `maximum_quantity`;
- `bingx-vst-execution-policy-v1`: `schema_version`, `execution`, and
  `risk_limits`; `execution` contains exactly `risk_percent`, `leverage`, and
  `maximum_exposure_ratio`, while `risk_limits` contains exactly
  `max_consecutive_losses`, `circuit_breaker_cooldown_minutes`, `max_drawdown`,
  `max_positions`, `max_portfolio_risk`, `max_daily_loss`, `max_margin_usage`,
  `max_position_size`, and `max_leverage`.

Decimal values are canonical decimal strings. Account and constraint
`observed_at` values are exact UTC timestamps ending in `Z`, and their snapshots
and the latest candle must satisfy the existing five-minute freshness window
(with the existing five-second future tolerance). The account file must carry
the operator's fresh account, portfolio, and explicit kill-switch/circuit-breaker
state; the constraints file must be a fresh operator-supplied instrument
snapshot. Preparation requires the execution policy to evaluate the frozen risk
pipeline at the canary's worst admitted leverage of exactly `2`; the resulting
normalized entry notional must also be at most `10`. These local caps are
rechecked from current VST state by the separate dry-run command. Artifact
expiry is deterministically the final canonical candle timestamp plus the
existing five-minute TTL; the validation clock is never serialized or hashed.

On approval, the command exclusively creates
`.operator-artifacts/<intent_id>.json` and prints one canonical compact report.
The artifact contains only the exact canonical `ExecutionIntent` bytes. A
`READY` report contains exactly `status`, `artifact_path`, `intent_digest`,
`symbol`, `side`, `expires_at`, `proposal_id`, `decision_id`,
`risk_evaluation_id`, and `reason_codes`. A blocked/no-action report has no
artifact path or intent digest. The proposal and decision identifiers come from
the frozen deterministic services; source-document SHA-256 digests bind the
market, account, constraints, and policy inputs; `risk_evaluation_id` binds the
exact frozen risk call/result and those inputs; and `intent_digest` is SHA-256
over the exact persisted bytes. Every source digest is supplied explicitly and
must match its file before any pipeline service runs.

Verify the generated artifact independently and compare it with the
`intent_digest` in the `READY` report:

```powershell
(Get-FileHash -Algorithm SHA256 "<READY_REPORT_ARTIFACT_PATH>").Hash.ToLowerInvariant()
```

Canonicalization and hashing prove local byte integrity, not exchange
provenance or currentness. The account/risk-state and constraint snapshots are
operator supplied and are not attested by BingX. There is no automatic shared
risk-state checkpoint, persistence, or cross-process synchronization. The
preparation command reads the four named files and writes the ignored local
artifact only: it reads no environment or dotenv values, requests no
credentials, performs no network call, and exposes no exchange read or write.

After reviewing a `READY` report and its artifact, run only the separate Phase
1I-1 dry-run handoff:

```powershell
python scripts/bingx_vst_demo_order.py `
  --intent-file "<READY_REPORT_ARTIFACT_PATH>" `
  --intent-digest "<READY_REPORT_INTENT_DIGEST>" `
  --host https://open-api-vst.bingx.com
```

Inspect the resulting `DRY_RUN_READY` report and stop before submission. Phase
1I-2 never supplies `--execute`, types an approval, or performs an order write;
any later Phase 1I-1 execution remains a separate operator-controlled event.

## BingX VST Demo order canary

The canary is an explicitly manual tool. Its default dry run performs
readiness and authoritative contract, order-book, account, leverage, position,
and order-history reads, but no exchange write:

```powershell
python scripts/bingx_vst_demo_order.py `
  --intent-file "<CANONICAL_READY_INTENT.json>" `
  --intent-digest "<INTENT_SHA256>" `
  --host https://open-api-vst.bingx.com
```

After reviewing the canonical `DRY_RUN_READY` report, execution requires the
newly rebuilt plan to have the exact approved digest:

```powershell
python scripts/bingx_vst_demo_order.py `
  --intent-file "<CANONICAL_READY_INTENT.json>" `
  --intent-digest "<INTENT_SHA256>" `
  --host https://open-api-vst.bingx.com `
  --execute `
  --plan-digest "<DRY_RUN_PLAN_DIGEST>"
```

The operator must then type the displayed `SUBMIT <CLIENT_ORDER_ID>` text
exactly. Both credentials are collected with `getpass`; neither command accepts
credential flags or loads environment/dotenv values. The safe sequence is:

1. obtain a canonical `READY` intent through the approved decision, frozen-risk,
   and execution-intent pipeline;
2. run dry mode and inspect the symbol, exact normalized fields, VST host,
   bounds, expiration, client ID, and plan digest;
3. independently confirm that the account has no same-symbol position and that
   leverage is already within the canary cap;
4. rerun with `--execute` and the reviewed digest, then type the exact client-ID
   confirmation;
5. inspect the final query/cancel/reconciliation report.

The write is one protected `LIMIT` submission with automatic write retries
disabled. Immediately before that write, the tool repeats the deterministic
client-ID absence check and revalidates constraints, the latest book,
same-symbol positions, leverage, position mode, and open entry orders. It then
queries by client ID, cancels once if still open, queries again, and reconciles
current state. An ambiguous submit,
including an unusable successful response, is resolved only by client-ID query
and is never blindly resubmitted. Any partial or full fill activates the
report's fail-closed kill-switch state and requires manual account inspection;
the tool never auto-flattens. Do not rerun after an ambiguous or unexpected-fill
report until the VST account has been reconciled. Live hosts and Live trading
remain unsupported.

## Tests and quality gates

The local equivalents of the blocking CI baseline are:

```powershell
python -m pytest
python scripts/scan_repository_secrets.py `
  --base-ref vst-runtime-freeze-v1
$ruffFiles = git diff --name-only --diff-filter=ACMR `
  exchange-freeze-v1..HEAD -- "*.py"
python -m ruff check $ruffFiles
python -m mypy --follow-imports=skip --ignore-missing-imports `
  main.py src/cli.py src/core src/data src/decision/__init__.py `
  src/decision/recorded.py src/decision/replay.py src/strategy src/risk `
  src/execution src/exchange/bingx_client.py src/execution_intent `
  src/paper_runtime src/vst_runtime `
  scripts/bingx_vst_demo_order.py `
  scripts/bingx_vst_prepare_intent.py `
  scripts/bingx_vst_readiness.py `
  scripts/bingx_vst_transport_diagnostic.py `
  scripts/scan_repository_secrets.py
python -m compileall -q src scripts main.py
python -m build
git diff --check exchange-freeze-v1..HEAD
```

The Ruff scope is all Python changed since the frozen exchange baseline. The
mypy command is the current project-compatible canonical/frozen scope. Full
audits are `python -m ruff check .` and
`python -m mypy --follow-imports=skip --ignore-missing-imports src`; their
pre-existing findings are recorded in [Tasks](docs/TASKS.md) rather than hidden
with configuration exclusions. Automated tests use fakes for VST readiness and
must not contact an exchange.

## Credential and repository security

- Never commit `.env`, credentials, API keys, secrets, tokens, signatures,
  private keys, response bodies, or signed query strings.
- `.env.example` contains placeholders only. Copy it only for legacy/local
  experimentation; the VST readiness script deliberately ignores it.
- Use VST-scoped, least-privilege credentials and rotate any credential that
  may have appeared in a terminal, log, patch, or repository.
- Do not add real values to test fixtures. Tests must use unmistakably fake
  constants and injected transports.
- Readiness output is sanitized and local readiness-output files are ignored.
- Phase 1I-2 intent artifacts are local operator material and
  `/.operator-artifacts/` is ignored; do not commit them or any source snapshot.
- Run the local secret scan before committing:
  `python scripts/scan_repository_secrets.py --base-ref vst-runtime-freeze-v1`.
  The stdlib/Git-only scanner checks committed additions, tracked/staged
  content, and non-ignored working files.
  It permits only a reviewed set of obvious fake test values and reports rule,
  path, and line metadata without printing a matched value.

## Current limitations

The repository contains older analysis, domain, shared-value-object,
backtesting, exchange, and execution surfaces alongside the canonical recorded
runtime. Their presence is not a claim that they are composed into an
end-to-end production system. The repository audit records the bounded dead
set removed in Phase 1H-2 and the compatibility boundaries that remain.

The following are intentionally deferred:

- automatic or unattended demo-order deployment;
- shadow and micro-live operation;
- unrestricted live trading;
- MT5 integration;
- production AI/ML decisioning;
- automatic multi-exchange orchestration;
- dashboard/API deployment;
- durable paper/VST state persistence and background operation.
- exchange-attested account/constraint input acquisition or a shared durable
  risk-state checkpoint for offline intent preparation.

The controlled progression is:

```text
recorded replay / paper
  -> read-only VST readiness
  -> repository and deployment hardening
  -> offline canonical intent preparation
  -> explicitly gated VST demo orders
  -> shadow operation
  -> micro-live operation
```

Each transition requires its own safety review. See the
[Roadmap](docs/ROADMAP.md), [Tasks](docs/TASKS.md), and
[Legacy Compatibility](docs/LEGACY_COMPATIBILITY.md).

## License

No license has been selected and no `LICENSE` file is present. Until that
decision is made, no permission to copy, modify, or redistribute is granted by
this repository. The decision remains a post-controlled-Demo governance item.
