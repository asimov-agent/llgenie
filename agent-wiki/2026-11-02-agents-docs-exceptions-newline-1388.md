# 2026-11-02 — restore trailing newline in docs-exceptions.json (#1388)

The #1385 proc-seam merge (`e91b42c9`) rewrote `tests/fixtures/docs-exceptions.json`
without a trailing newline, so `make lint` rejected it and `make ci-lint` went red on
`main` `f41685f3`.

This change appends the newline, returning the file to the lint contract (every
tracked text file ends with a newline). Verified: `make lint` rc=0, `make ci-lint`
rc=0, `make check-docs` rc=0 at head `60a3d62`.

The dispatch premise named `check-pr-closing`/`pr-closing-report` as undocumented; on
measure they are documented in `docs/BOTS.md` + `docs/ARCHITECTURE.md` and `make
check-docs` already reads rc=0 (291 targets documented) — they were not added as
exceptions because a stale exception entry is itself a check-docs defect.

## Issue

- Implements: #1388
- Fixes the main surface red introduced by: #1385

## Status

DONE (gate-restoring lint fix; awaiting owner-gated merge).
