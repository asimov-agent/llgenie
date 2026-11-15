# CI discipline gate: clocks off the bot lanes, allow-lists in a gate (issue #2701)

Issue: #2701. PR: branch `feat/ci-schedule-discipline` (number recorded when the PR is opened). OpenSpec change: ci-discipline-gate.

## What was verified
- Survey at base `dcfb96b7df`: 19 workflow files declare a `schedule:` key; the 8 deactivated lanes (architecture-bot `'47 */6 * * *'`, ci-requeue `'15,45 * * * *'`, issue-bot `'23 6 * * *'`, issue-dedupe `'51 */6 * * *'`, issue-refiner `'43 * * * *'`, registry-sync-review `'55 * * * *'`, search-smoke `'11 7 * * *'`, rebase-bot `'29 */6 * * *'`) lost exactly their `schedule:` blocks — `workflow_dispatch`/`repository_dispatch`/push/PR triggers unchanged.
- `scripts/check_ci_discipline.py` enforces four faces: `SCHEDULE_ALLOW` (new clock outside it = finding; allow-listed lane without a clock = stale-entry finding), tests-only pipelines (`ci.yml`, `pipeline.yml`, `all-pipelines.yml` — no agent marker), `AGENT_LANES` (agent users outside the list = finding; deactivated lane re-scheduling = finding), and the AGENTS.md section header + pin phrases. `make check-ci-discipline` rc 0 on the head.
- Gate-in-review finding: the first allow-list draft missed `publish-agent-image.yml` (builds/pushes the Hermes agent image) and `search-smoke.yml` (dispatch-only key proof via the sanctioned agent-fetch leg); both added with rationale strings before the commit.
- `tests/test_ci_discipline.py` green on the real tree and red against five fixture trees (new clock, stale allow-list, tests-only pipeline gains an agent job, deactivated lane re-schedules, AGENTS.md section removed); the 4 re-homed tests + `test_check_cron_drift.py` + `test_all_pipelines.py` pass together (88 tests).
- Wiring: `mk/gates.mk` (`check-ci-discipline`, `ci-discipline-report`), `mk/ci.mk` ci-unit chain, `scripts/package-layers.json` CI group, `scripts/issue_bot_gates.py` DEFERRED roster.
- AGENTS.md gained the durable section "CI pipeline discipline: weekly engine/registry lane only, tests-only main pipeline, Hermes in agent-image lanes only (mandatory, durable)".

## Current status
Umbrella #2701 stays open on purpose: its lanes #2702 (ci-requeue machinery retirement) and #2703 (re-home the deactivated bots' behaviour) are open and cite it back, so this change's PR references #2701 without the closing keyword. Branch `feat/ci-schedule-discipline`, one commit; unit suite + lane-preflight recorded in the PR trail.
