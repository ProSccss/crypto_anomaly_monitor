# DECISION_LOG

Purpose:

Store important project decisions and their rationale.

Only significant decisions belong here.

Do not store temporary implementation details.

---

# D-001

Title:
Remove volume_percentile from Gate A

Status:
ACTIVE

Reason:

Volume filter blocked many PRE_BREAKOUT setups and reduced research coverage.

Outcome:

Volume percentile no longer participates in Gate A.

---

# D-002

Title:
Remove EMS filter from PRE_BREAKOUT

Status:
ACTIVE

Reason:

PRE_BREAKOUT and EMS describe different market states.

EMS significantly reduced discovery of valid PRE_BREAKOUT setups.

Outcome:

PRE_BREAKOUT operates independently from EMS.

---

# D-003

Title:
Introduce setup_context

Status:
ACTIVE

Reason:

Need separate statistics for:

* RANGE_COMPRESSION
* TREND_COMPRESSION

Outcome:

Outcome tracking records context and reports are split by context.

---

# D-004

Title:
Cooldown before predictive_setup creation

Status:
ACTIVE

Reason:

Cooldown previously blocked Telegram notifications only.

Setups continued to be written into the database.

Outcome:

Cooldown executes before predictive_setup creation.

---

# D-005

Title:
Model Freeze V2.7

Status:
ACTIVE

Reason:

Insufficient outcome sample size for model changes.

Outcome:

Model changes are restricted until meaningful outcome statistics are collected.

Reference:

MODEL_FREEZE_V27.md

---

# D-006

Title:
Single-source market data principle

Status:
ACTIVE

Reason:

Indicators derived from different exchanges may become internally inconsistent.

Outcome:

Long-term architecture target is to derive all analytical signals for a symbol from a single primary exchange whenever technically feasible.

Reference:

ARCHITECTURE_PRINCIPLES.md

---

# D-007

Title:
Documentation is source of truth

Status:
ACTIVE

Reason:

Project knowledge must survive chat sessions and personnel changes.

Outcome:

Documentation takes precedence over chat discussions.

Reference:

START_HERE.md
CLAUDE_WORKFLOW.md

---

# D-008

Title:
Research API Layer (ResearchService)

Status:
ACTIVE

Reason:

Telegram commands (/analyze, /why, /features, /compare, /topscan), REST API,
Web UI, and Backtester all need the same symbol analysis logic. Without a shared
layer each consumer would duplicate PredictiveEngine calls and feature conversion.

Outcome:

- app/mappers/feature_mapper.py — infrastructure→domain boundary (FeatureSnapshotModel → FeatureSnapshot)
- app/services/research_service.py — ResearchService orchestration layer with three result types:
    SymbolState (lightweight, for batch), GateDiagnostics (gate gaps, for /why),
    SymbolAnalysis (full, wraps both + raw feature vector)
- GateDiagnostics uses tuple[GateRequirement, ...] — new gate conditions can be
  added without changing the dataclass structure
- Gate thresholds duplicated in research_service.py with explicit comment
  "Must exactly match PredictiveEngine._market_regime()" — consolidation into
  PredictiveEngine class constants is deferred until MODEL FREEZE is lifted (D-005)
- predictive.py is NOT modified (MODEL FREEZE constraint)

Architectural rule (new):
PredictiveEngine.classify() may only be called from MonitorService.poll_symbol()
(scanner pipeline — writes setups to DB, sends alerts) or ResearchService._analyze_model()
(research queries — read-only). No other call sites are permitted.

Reference:

MODEL_FREEZE_V27.md, D-005

---

# D-009

Title:
Research Layer is the only public entry point for model analysis

Status:
ACTIVE

Reason:

* Single point of analysis — every consumer (Telegram, REST API, Web UI, CLI,
  Backtester, future research tools) must see the same setup/regime/context
  decision for a given feature, computed the same way.
* Single point of diagnostics — gate gap calculations (GateDiagnostics) must
  not be reimplemented per-client; divergence would produce inconsistent
  /why explanations across surfaces.
* Single future home for explainability — any future "why this score" or
  feature-importance work attaches to ResearchService once, not per-client.
* Single point of caching — if live/historical analysis later needs caching
  (Phase 2/3), it is added once in ResearchService and benefits all clients.
* No duplicated analysis logic — prevents each new client from re-deriving
  feature_from_model conversion or classify() invocation independently.

Outcome:

PredictiveEngine is internal model implementation, not a public API.

External components (Telegram commands, REST API, Web UI, CLI, Backtester,
future research tools) MUST call ResearchService — never PredictiveEngine
directly.

Exception:

The operational scanner pipeline (MonitorService.poll_symbol()) remains a
permitted internal call site. It is part of the runtime detection pipeline
(writes predictive_setups, triggers alerts) and is not an external API
consumer of model analysis.

This formalizes the rule already established in D-008: PredictiveEngine.classify()
has exactly two legitimate call sites — MonitorService (operational) and
ResearchService (research/query). No third call site is permitted without a
new decision record.

Reference:

D-008, MODEL_FREEZE_V27.md

---

# D-010

Title:
MetricsService Runtime Observability Layer

Status:
ACTIVE

Reason:

Runtime metrics were distributed across MonitorService,
Telegram handlers and future infrastructure consumers.

This created a risk of duplicated counters and inconsistent
diagnostics between /health, /metrics, REST API and monitoring tools.

Outcome:

MetricsService becomes the single source of runtime engineering metrics.

Rules:

* Services record events.
* MetricsService owns runtime state.
* Consumers read MetricsSnapshot only.
* No component accesses internal counters directly.
* Metrics are runtime only.
* No database persistence.

Allowed consumers:

* Telegram Engineering commands
* REST API
* Web UI
* Monitoring exporters

Reference:

OBSERVABILITY.md