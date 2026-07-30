# Roadmap

The roadmap advances by explicit safety gates. A phase is complete only when
its code, tests, and boundary are present; file names alone do not establish a
capability.

## Completed baseline

| Phase | Status | Delivered boundary |
| --- | --- | --- |
| 1A - Packaging foundation | Complete | Python 3.12 package metadata, installable CLI, import-safe structure |
| 1B - Core runtime safety | Complete | Doctor-only CLI, explicit configuration, kernel, lifecycle, deterministic service graph |
| 1C - Data hardening | Complete/frozen | Canonical immutable market data, local service, recorded replay adapter (`data-freeze-v1`) |
| 1D - Recorded decision | Complete/frozen | Deterministic strategy proposal, frozen risk integration, recorded decision/replay (`decision-freeze-v1`) |
| 1E - Execution intent | Complete/frozen | Explicit account/risk/constraint/policy input and deterministic execution intent (`execution-intent-freeze-v1`) |
| 1F - Paper execution | Complete/frozen | Deterministic in-memory fills, protection, ledger, checkpoints, and reconciliation (`paper-runtime-freeze-v1`) |
| 1G-1 - BingX VST runtime | Complete/frozen | Fail-closed synchronous coordinator over injected `VstTransport` |
| 1G-2 - VST readiness | Complete/frozen | Async read-only BingX readiness and public transport diagnosis (`vst-runtime-freeze-v1`) |
| 1H-1 - Repository truth and CI baseline | Current | Authoritative docs, compatibility/audit inventory, security hygiene, and honest scoped CI |

The independently frozen risk, execution, and exchange libraries are marked by
`risk-freeze-v1`, `execution-freeze-v1`, and `exchange-freeze-v1`.

## Phase 1H-2 - Repository consolidation

Planned work:

1. Decide the canonical product identity and coordinate the repository,
   distribution, CLI, display-name, and import-namespace migration.
2. Migrate consumers away from alternate market-data models and normalizers.
3. Decide domain versus shared value-object ownership and migrate public/test
   consumers before removal.
4. Remove confirmed dead `_old`, empty scaffold, obsolete real-network, and
   typo files only after a separately reviewed removal manifest.
5. Resolve repository-wide Ruff and mypy debt, then replace the post-freeze
   scoped CI baseline with repository-wide static gates.
6. Reconcile or retire `requirements/*.txt` so dependency metadata has one
   maintained source.
7. Decide whether legacy dotenv settings and the websocket consumer remain
   supported; VST readiness must stay explicit/getpass-only.
8. Select a license and add it only after owner/legal approval.

Phase 1H-2 must preserve all frozen trading, risk, signing, request, fill, and
reconciliation semantics.

## Controlled deployment progression

### Stage A - Recorded replay and paper

Current supported execution environment. Continue deterministic replay,
checkpoint, restart, reconciliation, and adverse-event testing without network
or credentials.

### Stage B - Read-only VST

Current manual readiness boundary. It verifies public server time followed by
one authenticated balance read and one positions read. It cannot submit or
mutate anything.

### Stage C - Hardening

Phase 1H plus deployment controls:

- repository-wide static quality gates;
- canonical naming and contract consolidation;
- credential rotation/runbook ownership;
- operator authorization and auditable configuration;
- deterministic recovery and negative-path evidence;
- explicit network and exchange test separation.

### Stage D - VST demo orders

Deferred. Requires a separately approved composition root and operator command,
least-privilege VST credentials, order-notional/session/position limits,
idempotency evidence, cancel/reconcile recovery, sanitized audit output, and
tests proving that readiness remains read-only. It must not reuse the readiness
adapter for writes.

### Stage E - Shadow operation

Deferred. Consume live observations while generating decisions/intents without
submitting orders. Require drift, replay-equivalence, alerting, and long-running
reconciliation evidence.

### Stage F - Micro-live

Deferred and not authorized by this roadmap. Requires separate legal,
operational, security, capital, venue, monitoring, rollback, and incident
approval. Limits must be materially smaller than normal operation and live
enablement must remain explicit and reversible.

## Explicitly deferred product areas

- MT5 connectivity;
- production AI/ML or autonomous learning;
- automatic multi-exchange orchestration;
- dashboard/API deployment;
- general live trading;
- background schedulers, workers, and polling;
- durable production state storage.

Some library/scaffold code exists under these themes. None is a completed
runtime milestone.

## License decision

No license is selected and no `LICENSE` file should be added during Phase
1H-1. Phase 1H-2 must record the owner, intended distribution model, third-party
dependency obligations, and approval before adding license text.
