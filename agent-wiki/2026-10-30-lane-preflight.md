# 2026-10-30 — one pre-push target for a host lane: `make lane-preflight` (issue #1058)

A host lane can push a PR whose own head fails a gate that the fleet's `FAST_GATES` already covers,
and there was no single command that re-checked them before the push. `make bot-preflight` (issue
#792) fetches `main` and records the `AGENTS.md` sha but runs nothing; `scripts/issue_bot_gates.py`
defines the right set but only the issue-bot workflow runs it, and 16 workflows are disabled (issue
#902). Four PRs tonight each spent a full `linux/unit` matrix (~16–33 min) to reveal a red a
host-side gate catches in seconds: a malformed wiring fixture (#919, `check-wiring`), a missing
trailing newline (#919, `lint`), an unchecked OpenSpec task (#1056, `openspec-tasks-check`) and an
import-roots ratchet regression (#953, `check-import-roots`).

## What was added

- `scripts/lane_preflight.py` — runs the gates named by `FAST_GATES`, **imported** from
  `issue_bot_gates.py` (never restated, so #475's one-list property holds), prints `<gate>: rc=<n>`
  per gate and a final `preflight: OK|FAILED (n)`. It runs **every** gate (the issue-bot stops at
  the first red because it gates a push; a lane wants the whole picture), and it **refuses a dirty
  tree** — a tracked file differing from `HEAD` means the filesystem is not the would-be-pushed
  head, so the verdict would describe the wrong tree (the #919 failure mode).
- `make lane-preflight` — the target, `.PHONY`, documented in `make help` and `docs/BOTS.md`.
- `tests/test_lane_preflight.py` — 9 tests: the import identity (FAST_GATES is the same object),
  per-gate reporting and the OK/FAILED verdict, every-gate-runs-even-after-a-failure, the dirty-tree
  refusal, untracked-files-don't-block, a real ratchet regression reddening through `--gates`, and
  the make wiring.
- `AGENTS.md` — `make lane-preflight` named in the pre-push checklist.

## What was measured, not assumed

- `make lane-preflight` on a dirty worktree → exits 1, names the tracked file, refuses.
- `tests/test_lane_preflight.py` → 9 passed (containerised, `llgenie/test:latest`).
- A gate outside the fast six (`check-import-roots`) is runnable on demand via
  `--gates check-import-roots` without widening `FAST_GATES` — proving the #953 class is reachable.

## Scope

In: the target, negative controls, docs, AGENTS.md wiring. Out (per the issue): widening
`FAST_GATES` to `check-import-roots`, and the `host_bot_capabilities.py` generator defect.
