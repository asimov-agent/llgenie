# scheduled-engine-maintenance-timeouts — proposal

Issue: [#2317](https://github.com/asimov-agent/llgenie/issues/2317)

## Why

The four **step** jobs of the three scheduled engine/registry maintenance workflows carry no
`timeout-minutes`, so a hang inherits GitHub's 360-minute default:

- `engine-bump.yml` `plan` — git ls-remote + plan
- `engine-bump.yml` `bump` — pin + derive + apply + regen (incl. the live TensorFold archive test)
- `engine-bump-rebase.yml` `rebase` — forward-merge every open engine-bump PR
- `registry-sync.yml` `sync` — sync + render + test-unit

And no gate enforces it: `make check-workflows` and the two existing timeout-bounds suites
(`tests/test_engine_build_timeouts.py`, `tests/test_pipeline_timeouts.py`) only cover the
engine-*build* and pipeline/ci workflows. A future edit that drops a ceiling (or adds a new
unbounded scheduled job) lands green. This is standing rule `#1865` in its maintenance-blanket
form.

## What Changes

1. Give each of the four jobs a bounded `timeout-minutes` at the value its healthy run needs
   (measured from real runs — see `Technical`).
2. Add `check_scheduled_job_timeouts` to `scripts/check_workflows.py`: every non-`uses` job of a
   `schedule`-triggered workflow must declare a `timeout-minutes`. A `uses:` caller cannot carry a
   ceiling (issue #882), so only jobs that run steps are netted.
3. Prove it catches a regression: plant a job without a `timeout-minutes` and show the gate reds,
   then restore (the #1865 negative-control shape).

## Impact

- `.github/workflows/engine-bump.yml` (plan, bump)
- `.github/workflows/engine-bump-rebase.yml` (rebase)
- `.github/workflows/registry-sync.yml` (sync)
- `scripts/check_workflows.py` (new check, wired into `findings()`)
- `tests/test_workflows_valid.py` (five tests, incl. the repro-tree guard)
- `agent-wiki/2026-11-09-scheduled-engine-timeouts-2317.md`, `docs/changes.d/`, `CHANGES.md`

## Not covered

- **A workflow-level `timeout-minutes` default** — job-level ceilings are what a named run/job
  surfaces; a workflow-wide bound is a separate decision.
- **#2301's concurrency/cancellation** and **#2319 engine-build serving-leg** work — separate
  issues, separate PRs, not folded in here.

## Acceptance criteria

- [ ] `engine-bump.yml` `plan` and `bump` carry `timeout-minutes`; `engine-bump-rebase.yml`
      `rebase`; `registry-sync.yml` `sync`.
- [ ] `make check-workflows` reds when a `timeout-minutes` is dropped from any one of the four
      jobs, and is green otherwise (proven both ways on the PR's own head).
- [ ] `make lane-preflight` → `preflight: OK (6 gate(s))` on the PR head.

## Technical

- Measured at the PR head `32484a17` (rebased onto `origin/main@f99be26e`); issue filed at
  `main@5c7f4020`.
- Ceilings from real runs: `plan` 20 (12–27s run-wall: 42495434034, 41483337124, 41455039526),
  `bump` 30 (tensorfold 5m01s: 42495434034), `rebase` 20 (15s: 42478956638),
  `sync` 60 (32–40m: 40682255828, 40414178202, 40402053825) — width consistent with
  `registry-sync-review.yml`'s existing 60m.
- The gate's negative control is quoted in the PR body: removing `sync`'s 60 reds
  `make check-workflows` (rc=1) naming `registry-sync.yml`/`sync` and fails the repro-tree test;
  restoring returns green.
