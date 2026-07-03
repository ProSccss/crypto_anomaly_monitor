# CLAUDE_WORKFLOW.md

Mandatory workflow for all development work.

---

## Step 0 — Environment Verification

Before any development work:

Verify:

- repository path
- git branch
- latest commit

Commands:

git rev-parse --show-toplevel
git branch --show-current
git status

If repository path is incorrect:

STOP.

Do not modify files.

---

# Step 1 — Documentation Review

Before proposing any code changes, review:

1. START_HERE.md
2. PROJECT_STATUS.md
3. ARCHITECTURE_PRINCIPLES.md

Additionally:

## Research Tasks

Review:

- ROADMAP.md
- latest OUTCOME_REVIEW_*.md
- RESEARCH_NOTES.md

## Architecture Tasks

Review:

- ARCHITECTURE.md
- DECISION_LOG.md

## Model Tasks

Review:

- MODEL_FREEZE_V27.md
- DECISION_LOG.md

---

# Step 2 — Decision Review

Before proposing any architecture, model, threshold, indicator, feature, workflow, or process change:

1. Review DECISION_LOG.md.
2. Check whether a relevant decision already exists.
3. If a relevant decision exists:
   - reference it explicitly;
   - explain why it still applies or why it should be reconsidered.
4. Do not reintroduce previously rejected ideas without new evidence.

Required output:

```
DECISION REVIEW

Relevant decision:
<decision id or NONE>

Freeze conflict:
YES / NO

Recommendation:
PROCEED / RESEARCH ONLY / BLOCKED BY FREEZE
```

---

# Step 3 — Consistency Check

Before implementing changes answer:

- Does this conflict with ARCHITECTURE_PRINCIPLES?
- Does this conflict with MODEL_FREEZE_V27?
- Does this duplicate an existing decision?
- Does this conflict with ROADMAP?
- Does this require a new decision?

If any answer is YES:

Explain before writing code.

---

# Step 3.5 — Architecture Review

Before implementing architecture or service changes verify:

- Does the change introduce hidden coupling?
- Does it violate layer boundaries?
- Does it duplicate existing responsibilities?
- Can the same logic be reused by future features?
- Does it increase future maintenance cost?

Architecture should evolve by extending existing layers rather than creating parallel implementations.

If a new layer is introduced:

- clearly define its responsibility;
- define its public API;
- define what is explicitly outside its responsibility.

---

# Step 4 — Documentation Impact Review

Before every commit produce:

```
Documentation Impact

| Change | Document Update Required |
|--------|---------------------------|
| ...    | ...                       |
```

If no documentation updates are required:

```
Documentation Impact:
None
```

---

# Step 5 — Commit Readiness Review

Before proposing a commit verify:

- Architecture remains consistent.
- MODEL FREEZE rules are respected.
- Documentation is updated if required.
- DECISION_LOG is updated if required.
- PROJECT_STATUS is updated if required.
- No debug code remains.
- No temporary code remains.
- No accidental configuration changes remain.
- No unused imports, dead code or temporary helpers remain.

Only then propose a commit.

---

# Development Cycle

Every significant development task should follow the same lifecycle:

1. Documentation review.
2. Decision review.
3. Consistency check.
4. Architecture review.
5. Implementation.
6. Architecture audit.
7. Documentation update.
8. Code cleanup.
9. Commit readiness review.
10. Milestone tagging (when appropriate).

Skipping stages should be considered an exception rather than the normal workflow.

---

# Project Rule

Chat discussions are not a source of truth.

The documentation stored in the repository is the only authoritative description of the project.

New architectural decisions become valid only after they are documented.

If documentation and conversation conflict:

**Documentation wins.**

If documentation is incomplete:

**Update the documentation before relying on the new decision.**