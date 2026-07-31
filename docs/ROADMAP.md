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
| 1H-1 - Repository truth and CI baseline | Complete | Authoritative docs, compatibility/audit inventory, security hygiene, and honest scoped CI |
| 1H-2 - Bounded cleanup and governance | Complete | Reviewed dead/scaffold removal, obsolete network-script deletion, secret-scanning gate, and single dependency authority |

The independently frozen risk, execution, and exchange libraries are marked by
`risk-freeze-v1`, `execution-freeze-v1`, and `exchange-freeze-v1`.

## Phase 1H-2 delivered boundary

Phase 1H-2 intentionally did less than the earlier consolidation proposal:

1. removed only 24 source/script paths with complete zero-consumer evidence;
2. retired the two stale duplicate requirements files;
3. made `pyproject.toml` the sole dependency authority;
4. added regression coverage for removed imports and supported neighbors;
5. added a deterministic, value-redacting secret scan over repository content
   and committed changes;
6. retained consumer-backed compatibility and legacy dotenv settings with
   exact blockers documented.

It did not change frozen trading, risk, signing, request, readiness, execution,
fill, or reconciliation semantics.

## Post-controlled-Demo repository work

Unless proven to block operations, defer:

- repository/distribution/CLI/import-namespace renaming;
- MarketData contract consolidation;
- domain/shared value-object migration;
- generic decision/regime/normalizer consolidation;
- repository-wide Ruff cleanup;
- repository-wide mypy cleanup;
- further dead-code removal outside a new bounded manifest;
- license selection.

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

- blocking pytest and scoped static quality gates;
- deterministic tracked-content and committed-diff secret scanning;
- bounded dead/scaffold removal and authoritative dependency metadata;
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

No license is selected and no `LICENSE` file was added during either Phase
1H slice. Selection remains a post-controlled-Demo governance decision
requiring ownership, distribution-model, third-party-obligation, and approval
review.
