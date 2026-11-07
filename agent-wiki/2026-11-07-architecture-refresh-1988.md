# llgenie — #1988: docs(architecture) refresh for the tree at 20261107T1125

- **Date:** 2026-11-07 · **Issue:** #1988 (architecture-bot refresh drift)
- **Branch:** `agent/architecture-20261107T1125` (from `origin/main` `05185f9a`)
- **PR:** the ready-for-review PR closing #1988

## What changed

`docs/ARCHITECTURE.md` lagged the tree — last updated at `921dc8861ff2`, with 70 commit(s) and 460
changed path(s) since, so the document did not describe the code a reviewer was reading. The
architecture bot re-derived the surface and the drift from real git state (`make
architecture-bot-brief` -> `make architecture-bot-doc`) and rewrote only the doc; this PR carries
that one file on `agent/architecture-20261107T1125`.

## Verified

- `docs/ARCHITECTURE.md` is current at `05185f9a`; drift paths include `.github/workflows/ci.yml`,
  `.github/workflows/scope.yml`, `.github/workflows/engine-build.yml`, `Makefile`, `CHANGES.md`,
  `agent-wiki/2026-11-03-engine-build-timeout.md` and the `.hermes/skills/` tree — each re-measured
  against the real tree, not by eye.
- `make check-docs` rc=0 on the pushed head (guard + change-note trio present).
- Committed as `Asimov Agent <support@docondee.com>`; the bot never merges and never pushes to
  `main`.

## Decision

The refresh is a docs-only change with no behavioural surface: nothing under `scripts/`, `tests/`,
`containers/` or `.github/workflows/` moved on this branch — only `docs/ARCHITECTURE.md` plus this
note and its index row.
