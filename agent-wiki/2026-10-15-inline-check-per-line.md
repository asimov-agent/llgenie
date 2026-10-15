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
