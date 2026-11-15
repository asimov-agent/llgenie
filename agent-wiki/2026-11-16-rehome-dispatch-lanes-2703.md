# 2026-11-16 — re-home the deactivated bot lanes as event/dispatch-only (issue #2703)

OpenSpec change: `rehome-dispatch-only-lanes`. Branch `feat/2703-rehome-lanes`, PR opened against
upstream main closing issue #2703 (the re-home review leg of the umbrella #2701).

## Verified against the spec

- Classification decision (issue #2703, recorded in `scripts/check_ci_discipline.py::DISPATCH_ONLY_LANES`):
  ALL SEVEN deactivated lanes KEPT as event/dispatch-only; NONE retired. `issue-bot.yml` is
  keep-event-driven (`agent:implement` label + owner dispatch); architecture-bot, issue-dedupe,
  issue-refiner, registry-sync-review, search-smoke, rebase-bot are keep-dispatch-only — manual
  `workflow_dispatch` by the #2718 roster (owner, collaborator, GitHub itself). No retirement: the
  agent-executor scripts and their make targets are shared plumbing (`bot_claims`' rebase claim is
  how `engine-bump-rebase.yml` marks a PR taken) and the human dispatch path stays real.
- Gate (`check_ci_discipline.py`): the roster is a checked fact — a classified lane whose workflow
  file disappears, a dispatch-only lane that re-adds `on.schedule:`, or a kept lane missing its
  `# Triggered now (issue #2703):` header line is a finding naming the file; `report` prints all
  seven classifications. `tests/test_ci_discipline.py` pins both directions (16 tests, 5 new).
- Headers fixed: the stale "Trigger surface" wording ("every 6 hours", "its own schedule",
  "hourly", "fires daily at 07:11") corrected in all seven workflow files and in `docs/BOTS.md`
  (refiner/rebase-bot/search-smoke/registry-review prose), each workflow file now carries the
  trigger-marker line.
- Gates: `make check-ci-discipline check-workflows check-wiring check-docs openspec-validate
  rehome-dispatch-only-lanes test-unit` all rc=0 on the branch.

## Current status

Branch carries the OpenSpec change first, then the classification/header/gate commit; PR targets
upstream main with `closes #2703`. The umbrella #2701's remaining open legs stay separate issues.
