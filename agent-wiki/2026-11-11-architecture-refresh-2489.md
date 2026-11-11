# Refreshing docs/ARCHITECTURE.md for the tree at 20261111T0716 (issue #2489)

## What changed

`docs/ARCHITECTURE.md` lagged the tree again after the 2026-11-10 merge burst: its last
update was `5ecca957c3e6` and 11 commit(s) plus 115 changed path(s) landed since, so a
reviewer was reconstructing the shipped path from source. The architecture bot re-derived
the surface and the drift from real `git` state and rewrote only the doc. This is the
continuous-refresh pass that follows the 20261110T2017 census shipped via #2474; PR #2490
carries it.

The refresh carries the one file `docs/ARCHITECTURE.md` on `agent/architecture-20261111T0716`
(measured at `c6bf305e35ed1bfff2572278b0f67ec7c7aa1861`). The drift names the newer shipped
surface: the registry-sync job scoping (#2442), the product-manager and business-analyst
profile folds (#2355, #2388), and the agent-wiki notes from the 11-09/11-10 windows
(`acceptance-gate-circular-2094`, `agent-profile-fold-2169/2172/2177`,
`approver-merger-guard-2244`, `reactor-run-id-field`). The census pointer was re-pointed to
the same commit and its numbers re-counted there — 4500 tracked files, `openspec/` 1742
(449 changes), `agent-wiki/` 770, `docs/` 780, `agents/` 564, `tests/` 298 (255
`tests/test_*.py`, 236 in the gate) — verified by `make check-architecture-census`.

## Current status

The refresh commit carries `docs/ARCHITECTURE.md` plus this change-note trio and nothing else;
no workflow, make target, or script changed. The bot never merges and never pushes to `main` —
PR #2490 is for human review. This change-note trio (`agent-wiki/2026-11-11-architecture-refresh-2489.md`,
`docs/changes.d/2026-11-11-architecture-refresh-2489.md`, and its `CHANGES.md` index row) is the docs obligation the
refresh owed (`make check-docs`, issue #1123); issue #2489 is closed by PR #2490.
