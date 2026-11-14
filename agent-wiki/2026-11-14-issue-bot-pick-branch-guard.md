# 2026-11-14 — the issue-bot pick refuses issues whose lane branch exists (#2671)

OpenSpec change: `ci-issue-bot-pick-branch-guard` (issue #2671).

## What was verified

- **Measured defect** (issue #2671): `scripts/issue_implementer.py::dispatch()` computes
  `agent/issue-<n>-<slug>` but never checks the remote branch namespace, so it re-picked #744
  for days against two existing lane branches; each doomed run spent ~40 minutes and died at
  `git push ... [rejected] (fetch first)`. Three known-bad dispatches in the last 48h.
- **Fix**: new `_remote_lane_branches()` probe (`gh api repos/<repo>/git/refs/heads/agent/issue-<n>`,
  the refs prefix endpoint) with fail-open semantics — a 404 is "no branch", never a crash (the
  probe swallows `_gh`'s SystemExit). `_pick_free` now skips a candidate whose lane branch exists,
  naming the skip `branch-exists` with the branch; `dispatch` returns
  `action=none reason=branch-exists` + the skipped set when the candidate pool is exhausted that
  way, and a pinned (`FORCE_ISSUE`) dispatch onto a branched issue is refused BEFORE writing any
  claim comment. The CLI prints `reason=`; the workflow already maps `action=none` to
  `dispatch=false`, so no implement leg starts.
- **Tests** (`tests/test_issue_implementer.py`, subset-style per the issue's AC3): seeded foreign
  `agent/issue-7…` branch → pick takes #11 and the log names the branch; a fully branch-covered
  pool → `action=none`, `reason=branch-exists`, skips `[7, 11]`, no claim written; forced #11 with
  a lane branch → refused before claim; unseeded probes answer 404 and the dispatch is unchanged.
  Suite: 47 passed (43 pre-existing + 4 new) via `pytest tests/test_issue_implementer.py -q`
  rc=0; the hermetic `make test-unit` runs the same discovery lane in CI.
- **Not changed**: clearing #744's two lane branches and the six phantom runs stays owner
  territory (#2606 tracks the runs); this PR makes the burn impossible, it does not cancel
  anything.

## Decisions

- The probe is fail-open on purpose: a pick must never be aborted by a transient API failure —
  a missed skip costs one doomed leg (the old behaviour), an abort costs every dispatch.
- The refusal applies to forced pins too: the issue's scope names the pick decision, and a pin
  onto a branched issue is the same collision.

## Current status

Implementation + tests done in the `agent/issue-2671-pick-branch-guard` worktree; gates and PR
tracked on the issue.
