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
