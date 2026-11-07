# llgenie — #2013: docs(architecture) refresh for the tree at 20261107T1345

- **Date:** 2026-11-07 · **Issue:** #2013 (architecture-bot refresh drift)
- **Branch:** `agent/architecture-20261107T1345` (rebased from `origin/main` `58e10771`)
- **PR:** the ready-for-review PR closing #2013

## What changed

`docs/ARCHITECTURE.md` lagged the tree — last updated at `6012eb22774c`, with 6 commit(s) and 46
changed path(s) since, so the document did not describe the code a reviewer was reading. The
architecture bot re-derived the surface and the drift from real `git` state (`make
architecture-bot-brief` -> `make architecture-bot-doc`) and rewrote only the doc; this PR carries
that one file on `agent/architecture-20261107T1345`.

## Verified

- `docs/ARCHITECTURE.md` is current at `58e10771`; drift paths include `.github/workflows/ci-verdict.yml`,
  `CHANGES.md`, `agent-wiki/2026-11-07-ci-verdict-no-shell-interpolate-1972.md`,
  `agent-wiki/2026-11-07-orchestrator-tick-claim-liveness-1959.md`,
  `agent-wiki/2026-11-07-run-fixer-dedupe-marker-quote-1990.md`,
  `agents/llgenie-planner/skills/github-issue-triage/SKILL.md` and
  `docs/changes.d/2026-11-07-ci-verdict-no-shell-interpolate-1972.md` — each re-measured against the
  real tree, not by eye.
- `make check-docs` rc=0 on the pushed head (guard + change-note trio present).
- Committed as `Asimov Agent <support@docondee.com>`; the bot never merges and never pushes to
  `main`.

## Decision

The refresh is a docs-only change with no behavioural surface: nothing under `scripts/`, `tests/`,
`containers/` or `.github/workflows/` moved on this branch — only `docs/ARCHITECTURE.md` plus this
note and its index row.
