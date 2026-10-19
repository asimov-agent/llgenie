# agent-web-reach

## MODIFIED Requirements

### Requirement: The masked web reach is exercised by a monitored job

The repository SHALL run the masked fetch smoke from a scheduled workflow, on the
`FIRECRAWL_API_KEY` repository secret, with the agent-shell credential check as its first step and the
key forwarded by name only. The target SHALL NOT stay recorded as a human-run exception.

WHEN the scheduled workflow fires
THEN `make agent-shell-keys-check AGENT_SHELL_CHECK_KEYS=FIRECRAWL_API_KEY` runs before `make
search-smoke`, and a key that cannot reach the agent fails the run before any request is made.

#### Scenario: the smoke has its own scheduled slot

Given the repository's scheduled workflows,
When  the workflow files are read,
Then  one of them runs `make search-smoke` on a cron minute no other scheduled workflow owns.

- **Test:** `tests/test_agent_web_reach.py::test_the_smoke_runs_in_a_monitored_job_on_the_repository_secret`
  (the slot rule itself: `tests/test_bot_pipeline_isolation.py::test_no_workflow_shares_a_minute`)

#### Scenario: the agent's own shell is proven before the request is spent

Given a job that receives `FIRECRAWL_API_KEY`,
When  it starts,
Then  the agent-shell check runs with `AGENT_SHELL_CHECK_KEYS=FIRECRAWL_API_KEY` ahead of the fetch
      smoke, so a key Hermes strips from the agent's shell is loud instead of green.

- **Test:** `tests/test_agent_web_reach.py::test_the_smoke_runs_in_a_monitored_job_on_the_repository_secret`
  (the probe itself: `tests/test_agent_shell_keys.py`, live in the job: CI job `search-smoke.yml` →
  `make agent-shell-keys-check AGENT_SHELL_CHECK_KEYS=FIRECRAWL_API_KEY`)

#### Scenario: the key is never a value

Given the workflow that runs the smoke,
When  its text is read,
Then  the key appears only as `FIRECRAWL_API_KEY: ${{ secrets.FIRECRAWL_API_KEY }}` — never
      `-e FIRECRAWL_API_KEY=<value>`, never interpolated into a `run:` block.

- **Test:** `tests/test_agent_web_reach.py::test_the_smoke_runs_in_a_monitored_job_on_the_repository_secret`
  (the static rule: `make check-secret-output`)

#### Scenario: the human-run exception is deleted

Given `tests/fixtures/host-only-wiring.json`,
When  CI starts reaching `make search-smoke`,
Then  the recorded exception is gone, and the wiring guard fails a record that outlives its reason.

- **Test:** `tests/test_agent_web_reach.py::test_the_host_only_exception_for_the_smoke_is_gone`
  (the guard: `make check-wiring`)

#### Scenario: a dead or exhausted key is loud in CI

Given the scheduled job running on the repository secret,
When  the key is dead or out of credits,
Then  the run fails in seconds with the HTTP code the API returned, and never reports an empty result
      as success.

- **Test:** CI job `search-smoke.yml` → `make search-smoke` (the loud paths are locked hermetically by
  `tests/test_agent_web_reach.py::test_a_dead_key_fails_with_the_code_and_no_empty_success` and
  `::test_an_empty_body_is_not_healthy`)
