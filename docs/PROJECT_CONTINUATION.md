# Alpha Pro Ultimate Trader - Project Continuation

## SOURCE OF TRUTH

Repository:
alisolati61/DAlpha-Pro-Ultimate

Current development branch:
phase-1l-vst-controlled-execution

Baseline HEAD when this handoff was recorded:
979d670 - add gated VST execute-once operator

IMPORTANT:
main is NOT the current development truth.
At this checkpoint the active branch was 29 commits ahead of main and 0 behind.
The local working tree was clean.

---

# WORKING RULES

1. Continue from the current active/incomplete phase.
2. Never restart completed/frozen phases unless a proven defect requires reopening them.
3. PowerShell-first workflow is preferred while Codex/Claude quotas are unavailable.
4. ChatGPT designs bounded changes and provides PowerShell/safe-patch commands.
5. Only one editor/agent modifies the working tree at a time.
6. Claude Code should normally review read-only unless explicitly assigned implementation.
7. Codex may implement bounded work but must follow the same gates.
8. Never use:
   git add .
   git add -A
9. Never reset/stash/revert/overwrite existing work without an explicit reviewed reason.
10. Before commit:
    targeted tests
    regression tests
    quality checks
    git diff review
    acceptance gate
11. Trading/exchange writes must fail closed.
12. Risk has higher authority than Strategy or AI.
13. Unknown exchange state blocks further execution until reconciliation.
14. Restart must default to SAFE / UNARMED.
15. Live trading is a gated release stage, never an experiment.

---

# EXISTING TOOLING

tools/dev.ps1
- status
- focused
- vst
- quality
- verify
- full
- release

tools/operator.ps1
- VST watch
- rehearsal
- explicitly armed VST-only execute-once

tools/safe_patch.py
- fail-closed bounded patch recipes
- branch precheck
- clean-worktree precheck

Prefer extending these tools instead of large manual code edits.

---

# COMPLETED / FROZEN PROJECT PATH

1A  Packaging foundation                 COMPLETE
1B  Core runtime safety                  COMPLETE
1C  Data hardening                       COMPLETE / FROZEN
1D  Recorded decision                    COMPLETE / FROZEN
1E  Execution intent                     COMPLETE / FROZEN
1F  Paper execution                      COMPLETE / FROZEN
1G  BingX VST runtime/readiness          COMPLETE / FROZEN
1H  Repository hardening/governance      COMPLETE
1I  Controlled VST Demo pipeline         COMPLETE
1J  VST 3-minute canary timeframe        COMPLETE / FROZEN
1K  VST rehearsal command                COMPLETE / FROZEN
1L  Controlled VST execution             ACTIVE

Authoritative historic detail remains in:
docs/ROADMAP.md
docs/TASKS.md
docs/REPOSITORY_AUDIT.md

---

# MASTER ROADMAP TO LIVE

## 1L - Controlled VST Write Closure [ACTIVE]

Close the existing VST execute-once path.

Required evidence:
- VST readiness passes
- canonical capture/preparation
- READY execution intent
- dry-run/rehearsal passes
- approved immutable plan + SHA256
- explicit manual arm
- maximum one VST submission
- automatic write retry disabled
- query/cancel/final reconciliation deterministic
- no production host
- no duplicate submission
- no unresolved ambiguous exchange state
- no credential leakage

After acceptance:
freeze the controlled VST execution baseline.

---

## 1M - Repository & Quality Closure

Resolve production-relevant technical debt before Live progression.

Includes:
- tracked Ruff debt
- tracked mypy debt
- blocking CI quality gates
- secret/history scan
- dependency hygiene
- repository hygiene
- dead/legacy removal only after zero-consumer proof

Do NOT remove files only because their names appear duplicated.

---

## 1N - Durable Risk & State Authority

Persist safety state across crash/restart.

At minimum:
- peak balance/equity
- daily realized loss
- consecutive losses
- kill switch
- circuit breaker/cooldown
- execution intent IDs
- submitted clientOrderIds
- reconciliation checkpoint

Prefer transactional state storage such as SQLite.

Startup:
load durable state
-> read exchange state
-> reconcile
-> only then permit trading

Failure to reconcile = TRADING BLOCKED.

---

## 1O - Canonical Trading Runtime / Architecture Consolidation

Establish ONE production path.

Resolve:
- canonical runtime entry point
- canonical exchange/execution contract
- canonical decision engine
- canonical market-data contract
- canonical config/runtime modes
- duplicate/legacy live-reachable paths

No Strategy or Decision module may directly reach the exchange.

Required path:

Market Data
-> Strategy
-> Decision
-> Position Sizing
-> Risk
-> Execution Intent
-> Execution
-> Exchange

All alternate live-reachable bypasses must be removed or blocked before Shadow Live.

---

## 1P - Market + Strategy V1

Initial multi-timeframe trading model:

1H  = context/regime
30m = trend/structure
15m = entry/confirmation

Use a deliberately bounded first strategy.

Possible inputs:
- market structure
- EMA
- RSI
- ADX
- ATR
- volume
- liquidity
- BOS/CHOCH
- order-flow confirmation
- funding/open interest

AI remains:
filter
probability
regime
confidence

AI is NOT direct order authority.

---

## 1Q - Quantitative Validation & Risk Calibration

Required:
- LONG and SHORT
- fees
- slippage
- funding
- leverage/margin assumptions
- SL/TP
- trailing/partial exits where applicable
- portfolio equity curve
- concurrent-position effects

Validation:
In Sample
-> Out of Sample
-> Walk Forward
-> Monte Carlo
-> Stress Tests

Measure:
- expectancy
- profit factor
- max drawdown
- loss streak distribution
- risk of ruin
- Sharpe/Sortino where appropriate
- parameter stability

Previous conservative risk ideas such as:
~0.4% risk/trade
~2% daily loss
~5% max drawdown
<=5x leverage
small concurrent position count

are CANDIDATES only.
Final production limits must be validated here.

---

## 1R - 24/7 Paper Soak & Failure Injection

Run the production-equivalent pipeline with Paper execution.

Deliberately test:
- internet loss
- websocket disconnect
- API timeout
- malformed/partial response
- stale candles
- restart
- partial persisted state
- clock mismatch
- reconciliation mismatch

Acceptance requires:
duplicate execution = 0
risk bypass = 0
unresolved reconciliation = 0
state corruption = 0
stale-data trading = 0

Uncertainty must fail closed.

---

## 1S - Full BingX VST Trading

Move beyond one-shot canary.

Exercise complete Futures lifecycle:

OPEN
-> protection
-> monitor
-> manage
-> partial exit/trailing if applicable
-> CLOSE
-> PnL
-> state update
-> reconciliation

Test BUY and SELL.

Also validate:
- leverage
- margin
- position mode
- precision
- minimum notional
- reduce-only
- protections
- funding-related behavior

---

## 1T - Production Operations & Security

Required for unattended 24/7 operation:

- watchdog/process supervision
- health monitoring
- reconnect/backoff
- rate-limit monitoring
- structured logging
- Telegram/email alerts
- graceful shutdown
- safe restart
- state backup
- recovery runbook
- emergency kill
- least-privilege API
- NO withdrawal permission
- IP whitelist where supported
- hardened production deployment target

Production should not depend on a home PC remaining online.

---

## 1U - Shadow Live

Use real Live observations but make exchange writes impossible.

Generate:
WOULD_BUY
WOULD_SELL
WOULD_EXIT

Compare:
Backtest
Paper
VST
Live Shadow

Collect drift, replay-equivalence and reconciliation evidence.

No order submission capability.

---

## 1V - Micro-Live Canary

First real capital.

Start extremely bounded:
- BingX only
- initially very limited symbols
- maximum one position
- low leverage
- hard notional ceiling
- hard daily-loss limit
- hard drawdown limit
- kill switch
- no withdrawal permission
- IP whitelist

Restart must NOT auto-arm Live.

Restart path:
SAFE
-> load state
-> health checks
-> exchange reconciliation
-> explicit controlled arm

---

## 1W - Production Live V1

Scale only after successful Micro-Live evidence.

Increase in reviewed tiers:
- capital
- symbols
- concurrent positions
- leverage
- strategy breadth

Observe and approve each tier before the next.

End state:
24/7 Production Automated Trading System.

---

# POST-LIVE ULTIMATE EXPANSION

Only after Production Live V1 stability:

- advanced order flow
- smart money / whale intelligence
- on-chain
- news/sentiment
- advanced AI/ML research
- PPO/RL research
- portfolio allocation
- 8-12 exchanges
- forex
- stocks
- indices
- commodities
- options
- other asset classes

These must be modular additions and must not destabilize the live-critical core.

---

# DUPLICATE / LEGACY / DEFECT POLICY

Nothing observed is forgotten.

Critical/live-blocking defect:
fix immediately in the phase where discovered.

Repository/static debt:
primarily Phase 1M.

Architecture/source-of-truth duplication:
primarily Phase 1O.

Before 1U Shadow Live:
NO unresolved live-reachable duplicate or ambiguous production path may remain.

Examples to keep under review:
- duplicate/legacy Decision Engines
- overlapping market-data contracts
- overlapping config/contracts
- legacy compatibility code
- static-analysis debt
- stale/dead modules

Removal requires:
consumer/reference proof
-> targeted tests
-> removal
-> full regression

---

# FUTURE CHAT CONTINUATION INSTRUCTION

When continuing Alpha Pro Ultimate Trader:

1. Read this file first.
2. Read docs/ROADMAP.md.
3. Read docs/TASKS.md.
4. Check current branch and HEAD.
5. Check git status.
6. Check recent commits.
7. DO NOT assume main is current.
8. Resume the first ACTIVE/incomplete phase.
9. Do not restart frozen phases without a documented defect.
10. Prefer PowerShell-first / safe-patch workflow.

CURRENT NEXT ACTION:
Audit and close Phase 1L Controlled VST Write.
Do not add unrelated features before determining and passing its exact remaining acceptance gate.
