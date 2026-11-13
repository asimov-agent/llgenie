# Proposal: architecture-bot emits the note + row its own doc change owes

## Why

`make check-docs` enforces the change→note rule (issue #1123): a branch that changes a tracked
doc must add a matching `agent-wiki/<stem>.md` note and its `docs/changes.d/<stem>.md` row. The
architecture-bot's publish leg commits `docs/ARCHITECTURE.md` **alone** (workflow header: "never
commits a file other than the doc"), so every 6-hourly refresh reddens its own PR at ci-scope.
Measured on PR #2595 (issue #2594): run 43301454421 failed with
`[check-docs] ERROR: change->note: this branch changes docs/ARCHITECTURE.md but adds no
agent-wiki/<stem>.md note`; a human hand-paid the pair (commit `03f2883`-era follow-up) to land it.
Filed as issue #2598.

## What Changes

- `scripts/architecture_bot.py::publish` gains a deterministic pair step: after the doc is accepted
  (dirty, clean of strays) it writes `agent-wiki/<date>-architecture-refresh-<issue>.md`, the
  matching one-row `docs/changes.d/<stem>.md`, and rebuilds `CHANGES.md` via
  `changes_index.write` — all bot-authored, so the agent's "doc is the ONLY writable file" line
  and the `stray_changes` guard stay intact (the pair is generated AFTER the stray check).
- The bot commit adds the four paths (`doc`, note, fragment, `CHANGES.md`) in the same commit and
  same identity; the PR closes its issue exactly as before.
- `architecture-bot.yml` header comment updates "never commits a file other than the doc" to name
  the owed pair as the exception (the workflow already runs `make architecture-bot-publish` —
  no new steps).
- `tests/test_architecture_bot.py` is extended in place: the publish test asserts the four-path
  commit, the fragment row parses, and the note link matches the fragment stem; dry-run/files-
  nothing tests assert no pair files are written.

## Impact

- Affected specs: `architecture-bot` (new capability `architecture-bot-doc-pair`)
- Affected code: `scripts/architecture_bot.py`, `.github/workflows/architecture-bot.yml` (comment),
  `tests/test_architecture_bot.py`
