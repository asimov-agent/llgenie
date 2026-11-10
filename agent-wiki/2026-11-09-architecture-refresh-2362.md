# Refreshing docs/ARCHITECTURE.md for the tree at 49c63357 (issue #2362)

## What changed

`docs/ARCHITECTURE.md` lagged the tree: last updated at `ffbde9136553`, it was behind by
18 commit(s) / 159 changed path(s), so the document no longer described the code a
reviewer was reading. The architecture bot re-derived the surface and the drift from real
`git` state and rewrote only the doc.

The refresh carries the one file `docs/ARCHITECTURE.md` on `agent/architecture-20261109T0732`
(measured at `49c63357ab683ab55dbb430101d462f7ef8108c3`). Notable deltas in the re-derivation:

- Repository-layout census re-measured: 3989 → 4107 tracked files; the nine named content
  dirs now sum to 4029; `agent-wiki/` 693 → 717, `openspec/` changes 405 → 421,
  `docs/` 702 → 726, `tests/` 286 → 290.
- The structural-gates row records `check_task_shape.py` (issue #2123) and
  `verify_lane_contract.py` + `agent_lanes_check.py` (the manifest-roster contract,
  issue #2260); `scripts/check_engine_pins_published.py` prose is updated for the
  committed-set sweep and the registry-liveness monitor (issues #2190, #2270 family).
- The bots-and-automation row adds `reclaim_tmp_worktrees.sh` (issue #2141).
- The engine-build gate is now stated as **binary-only** (issue #2319): `make
  test-published-engine` checks digest + binary `-h`/`--version`; serving conformance stays
  host-only (`make test-engine-host` / `--serve`).
- `.github/workflows/engine-build.pr-trigger.yml` prose notes a pending push build waits in
  FIFO behind an in-flight one instead of being cancelled (issue #2301).
- The four scheduled engine/registry step workflows are hard-bound with a per-job timeout
  gate so a schedule-triggered run cannot hang the board (issue #2325).
- `ci-verdict` says a RED verdict names the failing jobs it found, never a bare "0 failures"
  (issue #2061).

The architecture bot never merges and never pushes to `main`; it only refreshes the doc and
opens the PR for a human review. The next 6-hour run stays quiet until the tree moves again.

## Verification (what this change proves)

- `docs/ARCHITECTURE.md` is at parity with the tree at `49c63357` (the census `measured at`
  commit it names; `make check-architecture-census` counts that exact `git ls-tree` snapshot).
- Only `docs/ARCHITECTURE.md` is committed on this branch, as `Asimov Agent
  <support@docondee.com>`; no workflow, make target or script changed.
- Change-note trio present: this note + `docs/changes.d/2026-11-09-architecture-refresh-2362.md`
  + the `CHANGES.md` index row — with `make check-docs` green at the head.

## Decisions / scope

- This is a **docs-only refresh**. Drift paths the document records as events in CI
  (`.github/workflows/*.yml`, `Makefile`, bump notes, etc.) are documented, not changed.
- No acceptance-checkbox content changes, no issue-body edits, no merge, no arm (#1088).

## Issue / PR

Implements #2362 via PR #2363. Docs-only; nothing merged, never armed (#1088).
