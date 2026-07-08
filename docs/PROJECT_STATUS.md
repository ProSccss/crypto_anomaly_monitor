# Crypto Anomaly Monitor — Project Status

Last Updated: 2026-07-05

## Project Snapshot

Version:
V2.8 Engineering Sprint E-1

Branch:
research/v2.8

Model State:
MODEL FREEZE

Primary Exchange:
Bybit

Complete Outcomes:
99

Research Phase:
Outcome Collection

---

## Runtime Status

Telegram Command Framework
VERIFIED ✅

Research API
VERIFIED ✅

Outcome Tracker
VERIFIED ✅

Dashboard
VERIFIED ✅

Docker Deployment
VERIFIED ✅

MetricsService
VERIFIED ✅ (deployment verification 2026-07-05)
(re-implemented 2026-07-03 after workspace mismatch —
an earlier VERIFIED record predated any committed code)

/metrics Command
VERIFIED ✅ (deployment verification 2026-07-05)

/why Command
VERIFIED ✅
deployment verification 2026-07-05
(commit 2e803bb; /help, /why LABUSDT, /why BTCUSDT
no-data state all PASS in deployed container)

/compare Command
VERIFIED ✅
deployment verification 2026-07-05
(commits cdfe642 + da8e1ac; multi-symbol comparison,
no-data handling, usage guard, shared formatting
regression all PASS in deployed container)

/topscan Command
VERIFIED ✅
deployment verification 2026-07-05
(commit da8e1ac; /help visibility, 21-symbol radar,
gate limiting diagnostics all PASS in deployed container;
/compare regression via shared formatting PASS)

Lifecycle Replay Dataset (IVS-2.1)
IMPLEMENTED ⏳ pending deployment verification
(lifecycle_replay_export.py + scripts/export_research.py:
chronological per-minute replay CSV — OHLCV, price features,
EMA research grid, derivatives, stored CAM state, future
behaviour windows, empty research labels; read-only)

Research Export Layer (IVS-1.4)
VERIFIED ✅
deployment verification 2026-07-05
(commit 9505eb2; docker build + restart PASS; runtime
export executed in production container — export_json
228,812 bytes, export_csv 119,972 bytes, full 23-column
CSV schema verified incl. IVS fields and research_labels)

Outcome Dataset Expansion (IVS-1.3)
IMPLEMENTED + DEPLOYED ⏳
WAITING FOR FIRST POST-IVS-1.3 COMPLETED OUTCOME
(commit a383ed8; docker build + container restart PASS;
migration 0011→0012 applied and schema verified;
existing MFE/MAE data confirmed intact in production;
new passive fields: time_to_peak_minutes, max_drawdown,
evaluation_duration_minutes — full VERIFIED pending the
first completed outcome populating them)

Manual Research Labels (IVS-1.2)
VERIFIED ✅
deployment verification 2026-07-05
(commit 306e710; docker build + container restart PASS;
alembic 0010→0011 applied — research_labels column on
setup_outcomes; passive storage only)

Model Version Tracking (IVS-1.1)
VERIFIED ✅
deployment verification 2026-07-05
(commit 7a82279; alembic 0009→0010 applied, both
model_version columns present, application startup,
scheduler and scanner PASS in deployed container)

Current Runtime
research/v2.8

Research Console
ACTIVE

---

## Active Components

* Outcome Tracking
* Outcome Dashboard
* Daily Telegram Research Report
* Predictive Engine V2.7
* GitHub Repository
* Research Documentation
* Telegram Command Framework (V2.8): /help, /status, /health, /metrics, /daily, /report, /analyze, /why, /compare, /topscan
* Research Console commands (V2.8):
  /analyze SYMBOL — real-time research analysis
  /why SYMBOL — explain setup drivers
  /compare SYMBOL SYMBOL [...] — compare symbols side by side
  /topscan — market radar over monitored symbols
* Research API Layer (V2.8): ResearchService, SymbolState, GateDiagnostics, SymbolAnalysis
* MetricsService (E-1):
  Runtime observability layer,
  MetricsSnapshot provider for /health, /metrics and future monitoring

---

## Current Engineering Priorities

1. Upgrade Health diagnostics
2. Improve structured logging
3. Continue Framework stabilization

---

## Next Research Priorities

1. Improve Telegram Research UX
2. Continue outcome analysis

---

## Engineering Sprint

Current Sprint:
IVS — Intelligence Validation Sprint

Focus:

* Model identity tracking
* Outcome validation infrastructure
* Research labeling
* Research export

Completed:

IVS-1.0 Current Data Model Audit — ACCEPTED
IVS-1.1 CAM model identity tracking — VERIFIED 2026-07-05
(residual check: first new setup should show
model_version = "CAM_V2.7_FREEZE")
IVS-1.2 Manual Research Labels storage — VERIFIED 2026-07-05
(setup_outcomes.research_labels JSONB, migration 0011;
NULL = unlabeled, no backfill; written only via
Repository.update_research_labels — never read by
scanner, evaluator, alerts, or scoring)
IVS-1.4 Research Export Layer — VERIFIED 2026-07-05
(commit 9505eb2; ResearchExportService, read-only join of
setups ⋈ outcomes ⋈ instruments; runtime export executed
in production container: JSON 228,812 bytes / CSV 119,972
bytes, full 23-column schema verified)

Current Task:

IVS-2.1 Coin Lifecycle Replay Dataset Infrastructure

Status:
IMPLEMENTED — pending deployment verification
(read-only replay export: one row per stored 1m candle;
microcap EMA research grid 60/120/180/240 × 1m/3m/5m —
UNVALIDATED hypothesis, export only; future behaviour
windows 15m–24h; CLI scripts/export_research.py; dataset
documented in docs/RESEARCH_DATASET.md)

Pending Verification:

IVS-1.3 Outcome Dataset Expansion

Status:
IMPLEMENTED + DEPLOYED — waiting for first post-IVS-1.3
completed outcome before marking VERIFIED
(deployment 2026-07-05, commit a383ed8: migration
0011→0012 applied, schema PASS, existing outcome query
PASS — MFE/MAE data intact; three new passive fields on
setup_outcomes; mfe_1h/4h + mae_1h/4h from the IVS-1.3
spec already existed since migration 0005 and were not
re-added; existing metric formulas unchanged and pinned
by tests)

Verification gate:
First outcome completing after deployment must show
time_to_peak_minutes, max_drawdown and
evaluation_duration_minutes populated, with existing
metrics unchanged. Outcomes complete ~12h after setup
creation — check after the next setup fires.

Previous Sprint:
E-1 Platform Stabilization — COMPLETE, all components VERIFIED

Note (E-1 history):
E-1.2 MetricsService was re-implemented together with E-1.3.
The earlier E-1.2 implementation existed only in documentation
(workspace mismatch — no code was ever committed), so its
prior VERIFIED status was recorded in error.

---

## Freeze Conditions

No model changes until:

* 150+ complete outcomes total
* 50+ complete outcomes per regime

Exceptions:

* Bug fixes
* Monitoring improvements
* Reporting improvements
* Documentation updates

---

## Current Findings

Observed:

* CONTINUATION currently outperforms PRE_BREAKOUT
* LONG currently outperforms SHORT
* HUSDT is the strongest observed symbol
* PRE_BREAKOUT + RANGE_COMPRESSION is currently the weakest setup family

Status:

Statistical significance is still insufficient for major model decisions.

---

## Research Focus

Primary Investigation:

PRE_BREAKOUT + RANGE_COMPRESSION

Questions:

* Why is hit rate extremely low?
* Which features separate winners from losers?
* Can additional filters improve expectancy?

---

## Next Review Milestone

150 complete outcomes

Review Date:
TBD (outcome-driven)

---

## Notes

Engineering platform foundation is stable.

Current Engineering focus:
increase reliability, observability and maintainability.

Research development continues after Engineering stabilization milestones.

Primary objective:

Transform research results into clear,
actionable information for traders.

---

Last Documentation Review:
2026-07-05

Documentation Status:
CURRENT