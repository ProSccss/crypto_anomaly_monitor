# CLAUDE_WORKFLOW

Mandatory workflow for all development work.

---

## Step 1 — Documentation Review

Before proposing any code changes, review:

1. START_HERE.md
2. PROJECT_STATUS.md
3. ARCHITECTURE_PRINCIPLES.md

Additionally:

### Research Tasks

Review:

* ROADMAP.md
* latest OUTCOME_REVIEW_*.md
* RESEARCH_NOTES.md

### Architecture Tasks

Review:

* ARCHITECTURE.md
* DECISION_LOG.md

### Model Tasks

Review:

* MODEL_FREEZE_V27.md
* DECISION_LOG.md

---

## Step 2 — Decision Review

Before proposing any architecture, model, threshold, indicator, feature, workflow, or process change:

1. Review DECISION_LOG.md.
2. Check whether a relevant decision already exists.
3. If a relevant decision exists:

   * reference it explicitly;
   * explain why it still applies or why it should be reconsidered.
4. Do not reintroduce previously rejected ideas without new evidence.

Required output:

DECISION REVIEW

Relevant decision: <decision id or NONE>

Freeze conflict:
YES / NO

Recommendation:
PROCEED / RESEARCH ONLY / BLOCKED BY FREEZE

---

## Step 3 — Consistency Check

Before implementing changes answer:

* Does this conflict with ARCHITECTURE_PRINCIPLES?
* Does this conflict with MODEL_FREEZE_V27?
* Does this duplicate an existing decision?
* Does this conflict with ROADMAP?
* Does this require a new decision?

If any answer is YES:

Explain before writing code.

---

## Step 4 — Documentation Impact Review

Before every commit produce:

Documentation Impact

| Change | Document Update Required |
| ------ | ------------------------ |
| ...    | ...                      |

If no documentation updates are required:

Documentation Impact:
None

---

## Step 5 — Commit Readiness Review

Before proposing commit verify:

* Architecture remains consistent.
* Freeze rules are respected.
* Documentation updated if required.
* No debug code remains.
* No temporary code remains.
* No accidental configuration changes remain.

Only then propose commit.

---

## Project Rule

Chat discussions are not a source of truth.

Documentation is the source of truth.

If documentation and conversation conflict:

Documentation wins.
