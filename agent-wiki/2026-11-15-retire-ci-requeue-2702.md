# 2026-11-15 — retire the ci-requeue re-rerun lane (issue #2702)

OpenSpec change: `retire-ci-requeue`. Branch `feat/2702-ci-requeue-retirement`, PR opened against
upstream main closing issue #2702 (lane of the umbrella #2701; #2703 stays open).

## Verified against the spec

- Deleted: `.github/workflows/ci-requeue.yml`, `scripts/ci_requeue.py`,
  `tests/test_ci_requeue.py`, and the `ci-requeue-cancelled` make target (`mk/ci.mk` recipe +
  Makefile `.PHONY` roster). The lane's `schedule:` had already been removed on `main` by the
  ci-discipline-gate change (#2701/#2704); this removes the remaining manual-reachable surface.
- Rerun rule (spec ADDED requirement): no repo mechanism calls `gh run rerun`/dispatch to re-run
  CI runs outside the allow-listed lanes. `run_failure_reactor.py` and `fix_bot_sweep.py` now print
  "a rerun belongs to the GitHub UI, the owner's word (issue #2702 retired `make
  ci-requeue-cancelled`)" for a PENDING (cancelled) verdict; their tests assert the new text.
- `zero-job-pending.yml`'s only trigger is now `workflow_run` on `ci-frozen-reaper` (completed) —
  the surviving allow-listed queue sweeper — and `check_workflows.py`'s guard-derivation docstring
  names the new roster.
- Inventories pruned: `scripts/package-layers.json`, `tests/fixtures/import-roots-baseline.json`.
  Comment/doc references pruned or annotated RETIRED in `ci_verdict.py`, `all_pipelines.py`,
  `bots_restore_health.py`, `ci_frozen_reaper.py`, `ci-frozen-reaper.yml`, `ci-hf-live.yml`,
  `docs/BOTS.md` (lane row + target + scheduled paragraph replaced by a retirement note),
  `docs/ARCHITECTURE.md`, and the four agents-tree skill files that instructed a heal via
  `make ci-requeue-cancelled`.
- Gates: `make check-wiring check-workflows check-docs check-ci-discipline` +
  `make openspec-validate NAME=retire-ci-requeue` + `make test-unit` all rc=0 on the branch.

## Current status

Branch carries the OpenSpec change first, then the deletion/re-point commit; PR targets upstream
main with `closes #2702`. Out-of-scope re-home review remains issue #2703's lane.
