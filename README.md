# Alpha Pro X Infinity

Alpha Pro X Infinity is a Python 3.12 trading-system foundation focused on
deterministic, fail-closed decision and execution boundaries. The repository
currently supports local recorded-market replay, deterministic strategy and
risk decisions, canonical execution-intent construction, in-memory paper
execution, and an explicit read-only BingX VST readiness check.

Phase 1I-1 also provides a manual, two-step BingX VST Demo canary. It accepts
only a canonical `READY` execution intent, defaults to a read-only dry run, and
can submit at most one protected non-marketable limit order after exact digest
and typed client-ID approval. It is not registered in the installed CLI or
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
                          OR manual DemoOrderPlan canary
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

The controlled progression is:

```text
recorded replay / paper
  -> read-only VST readiness
  -> repository and deployment hardening
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
