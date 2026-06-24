# Crypto Anomaly Monitor — Product Roadmap

## Current Status

Version: V2.7.1

Status:

- MODEL FREEZE
- Outcome Tracking ACTIVE
- Dashboard ACTIVE
- Daily Reports ACTIVE

Main Objective:

Collect and analyze outcome statistics without modifying trading logic.

---

# Phase 1 — Statistical Validation

Goal:

Validate or invalidate the current model using real outcome data.

Data Sources:

- setup_outcomes
- outcome_dashboard
- daily outcome reports

Research Areas:

- PRE_BREAKOUT vs CONTINUATION
- LONG vs SHORT
- setup_context analysis
- symbol analysis
- regime + context + direction combinations

Success Criteria:

- 150–200 complete outcomes collected
- Stable statistics across major setup groups
- Identification of strong and weak setup populations

Rules:

- No model modifications before sufficient statistical evidence
- No threshold optimization before validation is complete

---

# Phase 2 — V2.8 Research

Potential research directions:

- Filter weak setup populations
- Improve context classification
- Improve directional accuracy
- Analyze time-to-target behavior
- Analyze setup quality segmentation

Candidate Research Topics:

- PRE_BREAKOUT + RANGE_COMPRESSION
- CONTINUATION execution timing
- LONG vs SHORT asymmetry
- Symbol-specific behavior

---

# Phase 3 — Trade Execution Layer

Goal:

Transform research findings into actionable trading rules.

Potential Features:

- Setup ranking
- Trade recommendations
- Risk scoring
- Position sizing
- Execution guidance

---

# Phase 4 — Portfolio Layer

Goal:

Operate multiple setups simultaneously.

Potential Features:

- Portfolio management
- Exposure control
- Capital allocation
- Performance tracking

---

Current Research Milestone:

150–200 complete outcomes