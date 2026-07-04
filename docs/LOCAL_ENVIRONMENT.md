# LOCAL ENVIRONMENT

Canonical local repository:

D:\Projects\Crypto\crypto_anomaly_monitor

Branch:

research/v2.8

Do NOT use:

C:\Users\Адмін\Documents\New project\crypto_anomaly_monitor

That location is deprecated.

Before development session:

Run:

git rev-parse --show-toplevel

Expected:

D:/Projects/Crypto/crypto_anomaly_monitor

Run:

git branch --show-current

Expected:

research/v2.8

---

## Workspace Verification

Claude Code (and any developer) MUST verify the workspace
before any work (CLAUDE_WORKFLOW.md Step 0):

- repository path matches the canonical path above
- branch matches the expected branch
- HEAD commit matches expectations

If any check fails: STOP. Do not modify files.

Reason:
E-1.2 was developed in a deprecated workspace copy and the
code never reached git while documentation recorded it as
VERIFIED (see ENGINEERING_CHECKLIST.md — Verification Rule).

---

## Synchronization

GitHub is the ONLY synchronization source between machines
and workspaces.

- Transfer code exclusively via git push / git pull.
- Never copy a repository between machines through cloud
  storage, archives, or file sync.

## Cloud Sync

Cloud sync tools (OneDrive, Google Drive, Dropbox) must NOT
manage the repository directory.

In particular, the .git directory must never be under cloud
sync management: partial or delayed sync of .git corrupts
the repository and creates divergent workspace copies.

The canonical path D:\Projects\Crypto\crypto_anomaly_monitor
is intentionally outside all cloud-synced folders. Keep it
that way.

## Antivirus

Antivirus software can temporarily lock files under
.git/objects during commits, checkouts, or fetches.

Symptoms:

- "unable to write object" / permission denied on .git paths
- intermittent failures of commit, checkout, or pull

Actions:

- retry the git operation first (locks are usually transient)
- if it repeats, add the repository directory to the
  antivirus exclusion list