# ci-discipline

## ADDED Requirements

### Requirement: a non-allow-listed workflow may not declare a schedule trigger

Only an explicit allow-list of workflows may declare `on.schedule:`; each allow-listed entry
carries a one-line rationale. Any `schedule:` trigger key in a workflow outside the
allow-list is a finding, naming the offending file — so a PR that silently adds a scheduled
lane reddens CI instead of absorbing a slot in the exhausted cron budget.

#### Scenario: a new lane declares a schedule and the gate fails

Given a fixture tree holding a workflow `my-bot.yml` that both is not in the allow-list and
declares an `on.schedule:` block, and a hospital of other workflows none of which declare a
schedule;

When `make check-ci-discipline` runs;

Then it exits non-zero and its output names `my-bot.yml` as the offending file, while
reporting the total number of forbidden `schedule:` declarations.

- **Test:** `tests/test_ci_discipline.py::test_extra_schedule_file_reds`

#### Scenario: an allow-listed workflow keeps its schedule and the gate passes

Given the real `.github/workflows/` tree and an allow-list that names every file that
genuinely declares a schedule;

When `make check-ci-discipline` runs;

Then it exits 0.

- **Test:** `tests/test_ci_discipline.py::test_real_tree_passes`

### Requirement: an allow-listed workflow may not lose its schedule

An allow-listed file that no longer declares `on.schedule:` is a finding — a stale
allow-list is itself a defect, exactly like a git-identity or host-only-wiring exception
that rots. Removing the clock from a sanctioned weekly lane must be a deliberate edit to
both the workflow and the allow-list, not a silent drift.

#### Scenario: an allow-listed file drops its schedule and the gate fails

Given a fixture tree where `registry-sync.yml` (allow-listed) has no `schedule:` trigger,
and the allow-list still records it as scheduled;

When `make check-ci-discipline` runs;

Then it exits non-zero and names `registry-sync.yml` as an allow-listed file that lost its
schedule.

- **Test:** `tests/test_ci_discipline.py::test_allowlisted_file_lost_schedule_reds`

### Requirement: the main pipeline carries no agent-leg or agent-image job

The test pipeline files `ci.yml` and `pipeline.yml` run tests only. A job in either that
uses the `./.github/actions/agent-leg` composite action, or references the agent image
(`agent-image-ref`, `make agent-image`, `fix-loop-image`), is a finding — the main pipeline
provably contains no LLM/agent job, gate-checked and not just true today.

#### Scenario: an agent job appears in ci.yml and the gate fails

Given a fixture tree where `ci.yml` declares a job using `./.github/actions/agent-leg`;

When `make check-ci-discipline` runs;

Then it exits non-zero and names `ci.yml` as carrying an agent-leg job.

- **Test:** `tests/test_ci_discipline.py::test_agent_job_in_test_pipeline_reds`

#### Scenario: ci.yml and pipeline.yml are agent-free on the real tree

Given the real `ci.yml` and `pipeline.yml`;

When `make check-ci-discipline` runs;

Then no agent-leg/agent-image finding is reported for either file.

- **Test:** `tests/test_ci_discipline.py::test_real_tree_passes`

### Requirement: an agent-leg-using workflow is in the agent-leg allow-list

A workflow that uses `./.github/actions/agent-leg` must be named in the agent-leg
allow-list — the dispatch-only bot lanes (architecture-bot, issue-bot, issue-refiner,
rebase-bot, registry-sync-review, fix-bot) and the engine/registry agent legs. An
agent-leg-using workflow outside the allow-list is a finding.

#### Scenario: an un-listed workflow uses the agent leg and the gate fails

Given a fixture tree where `ci.yml` uses `./.github/actions/agent-leg` and the agent-leg
allow-list names `ci.yml` nowhere;

When `make check-ci-discipline` runs;

Then it exits non-zero and names `ci.yml` as using the agent leg outside the allow-list.

- **Test:** `tests/test_ci_discipline.py::test_agent_leg_outside_allowlist_reds`

### Requirement: the durable AGENTS.md CI-discipline section is present

AGENTS.md must carry the CI-discipline section ("weekly engine/registry lane only; main
pipeline tests-only; Hermes in CI only inside agent-image engine/registry legs; the agent
never starts a CI pipeline manually"). The gate asserts the section exists, so the repo
law cannot be deleted silently — the same shape `check-main-ruleset` uses for its rule
section.

#### Scenario: AGENTS.md loses the section and the gate fails

Given a fixture AGENTS.md body with no CI-discipline section;

When `make check-ci-discipline` runs with `--root` pointing at a tree whose `AGENTS.md`
lacks the section;

Then it exits non-zero and names the missing section.

- **Test:** `tests/test_ci_discipline.py::test_missing_agents_section_reds`

### Requirement: the leave-in-schedule anchor is enforced

An allow-listed file that declares a schedule must declare at least one `- cron:` value.
A file that "keeps its schedule" but declares none is a stale-allow-list finding, the
same class as a lost schedule.

#### Scenario: an allow-listed file declares schedule with no cron and the gate fails

Given a fixture tree where an allow-listed file declares `on.schedule:` with no `- cron:`
entry;

When `make check-ci-discipline` runs;

Then it exits non-zero and names that file.

- **Test:** `tests/test_ci_discipline.py::test_allowlisted_schedule_no_cron_reds`
