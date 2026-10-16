# The inline-script check was per step block, so a `gh` step could hide a script call (#296)

## Why

`workflow-inline-scripts` (the reviewer bot's check for "every command a CI workflow runs must be a make
target") skipped a whole **step block** as soon as it contained a make call or any `gh api`/`gh pr`/... .
A step that orchestrates with `gh` — the shape most likely to grow a second script call — was therefore
never inspected, and `registry-sync.yml` had been calling `python3 scripts/engine_skill_gap.py report
--md` inside exactly such a step.

## What landed

- The scan is **per command (per line)**: a repo-script call without a `make` on the same line is a
  finding, wherever it sits in the step; orchestration-only lines still pass (`gh`/`git` invoke no repo
  script). The per-block exemption and its `GUARD_ALLOWED` constant are gone.
- `registry-sync.yml` now asks a make target for the same markdown: `gap="$(make engine-skill-gap-md)"`,
  backed by the new `engine-skill-gap-md` target (`scripts/engine_skill_gap.py report --md`).
- Tests pin the regression case (a `gh api` step with a script on another line IS a finding), the
  clearing case (`make` on the same line), and the self-consistency case (the check over the real tree
  finds nothing).
- The step's own test moved with the call: `tests/test_engine_skill_gap.py` pinned the sync step's
  shape as `"report --md" in body`, so changing the step turned `make test-unit` red
  (`test_the_weekly_sync_regenerates_the_gap_and_spawns_a_tracking_issue`) until the test pinned
  `make engine-skill-gap-md` instead. A workflow change is not done until the test that locks it agrees.

## Verification

- `tests/test_code_review.py`: **24 passed** in `llgenie/test:latest`.
- Proven on the real files: with the PRE-FIX checker and the pre-fix `registry-sync.yml`, the check
  reports **0** findings (the hole); with the per-line checker and the same workflow, it reports **1**
  naming `python3 scripts/engine_skill_gap.py` in the step "Open / update the sync PR".
- `make lint`, `make check-docs`, `make check-wiring`, `make check-dispatch-forms`, `make
  openspec-validate NAME=inline-check-per-line`.

## Still open

- #293 — the reviewer bot does not look at open PRs (a PR already fixing a finding does not suppress it).
- #295 — the trigger-guard audit (queued-alarm has no guard; four guards accept any collaborator level).
- #305 — measured while proving this fix over the real workflows: `_steps()` never ends a block (a
  workflow has no unindented line after the first `run:`), so it yields only a file's LAST `run:` block
  (`ci.yml`: `current=1` vs `real=20`). The per-command scan above is correct, but it is exercised only
  on that last block until #305 lands. Filed, linked both ways, and deliberately not folded in here.
  **Fixed by PR #326** (`feat/inline-check-all-steps`): `_steps()` now ends a `run:` block at the first
  line indented at or below the `run:` line, so every step is scanned (13 → 105 blocks over the tree).
- #317 — found while running `make loop` to verify this change: the loop's `test` stage runs
  `tests/test_install.py` in a `--rm` container with `HOME=/root`, where the install artifacts cannot
  exist, so the stage is red on every Linux host. Proven pre-existing on `29080c7` (6 failed, 1 passed).
  Filed as its own issue and **fixed by PR #322** (`feat/loop-test-host-install`); not folded in here.
