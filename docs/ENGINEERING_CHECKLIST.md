# Verification Rule

Before marking any component VERIFIED:

- implementation exists in git
- deployed container tested
- user-facing command/API tested

Reason:
Prevent repeat of documentation/code mismatch
(E-1.2 was recorded as VERIFIED while no implementation
had ever been committed).

---

# Operational Checks

Lessons from Sprint E-1.

## Session Start (workspace mismatch)

□ git rev-parse --show-toplevel matches the canonical path
  (LOCAL_ENVIRONMENT.md)

□ git branch --show-current matches the expected branch

□ HEAD commit matches expectations

□ git status reviewed before starting new work

## Documentation / Code Consistency

□ every status claim in docs is backed by a commit in git

□ status changes reference the verification evidence
  (date, deployed revision, commands tested)

□ before relying on a documented component, confirm the
  code actually exists on the current branch

## Git Health (object locking)

□ repository directory is not managed by cloud sync
  (.git must never be synced — LOCAL_ENVIRONMENT.md)

□ on "unable to write object" / permission denied under
  .git/objects: retry first, then check antivirus locking

□ after any failed git operation, re-run git status and
  git log to confirm repository integrity

---

# Telegram Command Framework

## Architecture

✅ Router

✅ Context

✅ Commands

✅ Listener

---

## Integration

☑ Listener started

☑ Updates received

☑ Commands parsed

☑ Router dispatch

☑ Handler entered

☑ Reply executed

☑ Telegram API success

☑ User received response

---

## Production

☑ /help

☑ /status

☑ /health

☑ /metrics

☑ /daily

☑ /report

☑ /analyze

☑ /why

☑ /compare

☑ /topscan

--- 

# Telegram Listener

☑ delete_webhook()

☑ polling started

☑ update received

☑ command dispatched

☑ reply delivered

---

## Feature Lifecycle

☑ Design

☑ Implementation

☑ Commit

☑ Push

☑ Build

☑ Deploy

☑ Runtime Verification

☑ Documentation Update

☑ Engineering Checklist Update

☑ Done

---

Status:

VERIFIED

Verification Date:
2026-07-02