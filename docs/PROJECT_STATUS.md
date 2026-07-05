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
* Telegram Command Framework (V2.8): /help, /status, /health, /metrics, /daily, /report, /analyze, /why
* Research Console commands (V2.8):
  /analyze SYMBOL — real-time research analysis
  /why SYMBOL — explain setup drivers
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
2. Implement /compare
3. Implement /topscan
4. Continue outcome analysis

---

## Engineering Sprint

Current Sprint:
E-1 Platform Stabilization

Focus:

* Observability
* Diagnostics
* Reliability
* Maintainability

Current Task:

E-1.3 /metrics command

Status:
VERIFIED — deployment verification passed 2026-07-05
(/metrics, /status, /health all PASS in deployed container)

Note:
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