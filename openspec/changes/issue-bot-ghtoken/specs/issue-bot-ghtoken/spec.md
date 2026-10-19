# issue-bot-gh-token — spec delta

Capability: `issue-bot-gh-token`
Issue: [#364](https://github.com/asimov-agent/llgenie/issues/364)

## ADDED Requirements

### Requirement: a leg's step exports every credential that leg forwards

For every bot workflow, the STEP that runs a make leg SHALL export each credential the leg forwards
with `-e` — at job level or on that step itself. A sibling step's `env:` SHALL NOT count.

WHEN a leg forwards `-e NAME`,
THEN the step that invokes it SHALL see `NAME`, or the suite SHALL fail naming the workflow, the job
and the variable.

#### Scenario: the implementer's step exports GH_TOKEN
Given `make implement-issue` forwards `NOUS_API_KEY`, `GH_TOKEN` and `TYPESAFE_API_KEY`,
When   the suite inspects the step of `issue-bot.yml` that runs it,
Then   all three are set for that step (job `env:` or the step's own `env:`).
- **Test:** `tests/test_agent_shell_keys.py::test_the_leg_a_workflow_calls_gets_its_keys_from_that_job`

#### Scenario: a sibling step's env does not count
Given a job whose implement step exports nothing and a later push step that exports `GH_TOKEN`,
When   the suite checks the implement step,
Then   it reports the key as missing.
- **Test:** `tests/test_agent_shell_keys.py::test_the_detector_actually_detects`

### Requirement: the credential is proven visible in the agent's shell

The agent-shell step in `issue-bot.yml` SHALL include `GH_TOKEN` in `AGENT_SHELL_CHECK_KEYS`, so the
#358 probe proves the agent's own shell can read the token.

WHEN the job proves its credentials,
THEN `GH_TOKEN` SHALL be one of the keys proven.

#### Scenario: the probe covers the token
Given the issue-bot job,
When   the suite reads its `make agent-shell-keys-check` step,
Then   the key list names `NOUS_API_KEY`, `GH_TOKEN` and `TYPESAFE_API_KEY`.
- **Test:** `tests/test_agent_shell_keys.py::test_every_bot_job_proves_the_agent_shell`
