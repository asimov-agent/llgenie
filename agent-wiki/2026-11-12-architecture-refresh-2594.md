# docs(ARCHITECTURE): refresh for the tree at `be92a32695` (issue #2594, PR #2595)

## What was verified

- `docs/ARCHITECTURE.md` had lagged the tree: last touched at `1e7daa279655`, with 6 commits and
  58 changed paths since (measured by the architecture bot's drift derivation from real `git`
  state on the 2026-11-12 20:33 cycle; drift paths included
  `.github/workflows/engine-build-pr-trigger.yml`, `.github/workflows/engine-build.yml`,
  `.github/workflows/registry-liveness.yml`, `Makefile`, and four engine-verify agent-wiki notes).
- The refresh rewrote only `docs/ARCHITECTURE.md` — no behaviour paths — exactly as the bot lane
  is scoped.
- ci-scope originally redded PR #2595 (`[check-docs] ERROR`, run 43301454421, log line 212): a
  branch that changes `docs/ARCHITECTURE.md` owes an `agent-wiki/<stem>.md` note and its
  `docs/changes.d/<stem>.md` row (issue #1123 rule). This note and its sibling fragment
  `docs/changes.d/2026-11-12-architecture-refresh-2594.md` are that owed pair; `make check-docs`
  passes with them present.

## Key decisions

- The pairing gap in the bot's own doc leg (it publishes a refresh without emitting its note +
  row) is NOT patched here — PR #2595 stays docs-only. It is filed as its own issue
  ("architecture-bot doc leg emits no agent-wiki note / changes.d row", linked from PR #2595's
  `Not covered`).

## Current status

- Branch `agent/architecture-20261112T2033` rebased onto `origin/main` `5ffc7cdc845687bf93756ae5e7a4c681040e04dc`,
  note + row added, `make check-docs` green locally; PR #2595 targets `main`, closes #2594, and
  waits on ci-scope/ci re-runs for the auto-merge chain.

Issue: [#2594](https://github.com/asimov-agent/llgenie/issues/2594). PR: [#2595](https://github.com/asimov-agent/llgenie/pull/2595).
