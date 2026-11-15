# CI discipline: only the weekly engine/registry lane keeps cron; main pipeline tests-only; hermes only in agent-image engine/registry legs; agent never starts CI manually (issue #2702)

## Why

Owner policy stated 2026-11-15: the ONLY weekly scheduled lane is the engine-bumping +
engine image-build + latest-models/inference-servers lane; every other GitHub cron lane
must be deactivated; the CI main pipeline runs tests only, no LLM; Hermes/LLM usage in CI
is limited to agent-image jobs whose purpose is fetching the latest engine servers, syncing
the registry, updating the engine list with new engines, and updating existing engines'
Dockerfiles; the agent never manually starts a CI pipeline (no `gh run rerun`, no
`gh workflow run`, no requeue loops).

Nothing in the repo encoded or enforced any of this. Measured on main `dcfb96b7`
(issue #2702): 37 workflow files, 26 declare an `on.schedule:` key (30 cron blocks), and
eight of them are autonomous bot/trigger lanes that run LLM/agent work or re-trigger the
pipeline on a clock — architecture-bot, ci-requeue, issue-bot, issue-dedupe, issue-refiner,
registry-sync-review, search-smoke, rebase-bot. The scheduled bot lanes spawn autonomous
agent runs that fan out into parallel issue lanes, contradicting the one-task-at-a-time
rule (the same reason Hermes *host* cron was banned, AGENTS.md 2026-11-14); `ci-requeue`
re-triggers pipelines outside GitHub's own event flow, so run counts stop being evidence;
and the repo already measured that its cron minute budget is exhausted
(`zero-job-pending.yml:14-16`). Today allow-list-vs-reality already disagrees: 30 cron
blocks, zero sanctioned list.

## What changes

1. Remove the `schedule:` trigger block from the eight lanes above. Their
   `workflow_dispatch:` / `issues:` / `issue_comment:` triggers stay — humans and GitHub
   events may still run them; only the clock is removed. PR landing/monitoring plumbing
   (auto-merge, arms, holds, queued-alarm, engine-bump-rebase, reaper, stale-branch-cleanup)
   keeps its cron.
2. Add ONE gate, `scripts/check_ci_discipline.py` + `make check-ci-discipline`, failing when:
   (a) any `schedule:` key appears outside an explicit allow-list of 18 files, each carrying
   a one-line rationale — the weekly engine lane `engine-bump.yml`, the weekly
   models/registry fetch `registry-sync.yml`, the weekly test battery `all-pipelines.yml`,
   the non-agent security/liveness monitors, and the merge/monitoring plumbing;
   (b) an allow-listed file loses its schedule (a stale allow-list is also a finding);
   (c) any agent-leg (`./.github/actions/agent-leg`) or agent-image job appears in the
   test-pipeline files `ci.yml`/`pipeline.yml` — the main pipeline stays tests-only;
   (d) an agent-leg-using workflow is outside the agent-leg allow-list; (e) the durable
   AGENTS.md CI-discipline section is missing.
3. Write the behavior into AGENTS.md as a durable section: weekly engine/registry lane only;
   main pipeline tests-only; Hermes in CI only inside agent-image engine/registry legs; the
   agent never starts a CI pipeline manually.
4. Wire the gate: `check-ci-discipline` in `mk/ci.mk` + `.PHONY`, in the `ci-unit` sequence,
   in `make lane-preflight`'s fast gate set, in the unit-suite roster/wiring, classified in
   `scripts/issue_bot_gates.py`, registered in `scripts/package-layers.json`, and locked by
   hermetic tests in `tests/test_ci_discipline.py` (copy-tree fixtures for both failure
   directions; AGENTS.md section assertion inside the gate itself).

## Open items

None. The deactivated lanes' behaviour retirement is its own issue (#2703, named in the
issue body's `Not covered`); this change only removes their clocks and adds the gate.
