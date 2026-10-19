# agent-web-reach — spec delta

Capability: `agent-web-reach`
Issue: [#362](https://github.com/asimov-agent/llgenie/issues/362)

## ADDED Requirements

### Requirement: the Firecrawl key is proven visible in the agent's shell

`FIRECRAWL_API_KEY` SHALL be a member of the Makefile's `AGENT_SHELL_KEYS`, so
`make agent-shell-keys-check` proves the agent's own shell can read it, and every leg that uses it
SHALL forward the plain name and the `_HERMES_FORCE_` twin.

WHEN a fetch leg starts,
THEN the key SHALL travel by NAME only, and its value SHALL NOT appear on a command line or in a log.

#### Scenario: the key is in the one list and forwarded by name
Given a sentinel `FIRECRAWL_API_KEY` and `make -n agent-fetch`,
When   the command is rendered,
Then   it carries `-e _HERMES_FORCE_FIRECRAWL_API_KEY` and the sentinel appears nowhere.
- **Test:** `tests/test_agent_web_reach.py::test_firecrawl_is_in_the_one_agent_shell_list`

### Requirement: one fetch leg, key read from the environment

`make agent-fetch URL=… OUT=…` SHALL be the only leg that fetches a URL. Its prompt SHALL read the key
from the environment, SHALL state that the value is never printed, echoed or written, and SHALL write
only the fetched markdown to `OUT`.

WHEN the leg runs,
THEN exactly one prompt names the scrape API, and it names the VARIABLE rather than embedding a value.

#### Scenario: the prompt names the variable and forbids printing it
Given the Makefile,
When   the suite reads the fetch recipe,
Then   it references `$$FIRECRAWL_API_KEY`, states the no-print rule, and no second prompt mentions
       `api.firecrawl.dev`.
- **Test:** `tests/test_agent_web_reach.py::test_the_fetch_prompt_reads_the_key_by_name_and_forbids_printing_it`

#### Scenario: the leg and its smoke are real make targets
Given the Makefile,
When   the suite looks for the targets,
Then   `agent-fetch`, `_agent-fetch` and `search-smoke` exist and the smoke runs
       `scripts/fetch_smoke.py`.
- **Test:** `tests/test_agent_web_reach.py::test_the_leg_is_a_make_target_and_the_smoke_is_reachable`

### Requirement: a dead key fails loudly and an empty result is never healthy

`scripts/fetch_smoke.py` SHALL read the key by name, make one bounded request, and exit non-zero with
the HTTP code on 401/402/403, and SHALL refuse an HTTP 200 that carries no `data.markdown`. A missing
key SHALL be exit 2 naming the variable; `--allow-unconfigured` SHALL be the only opt-out and no
workflow SHALL use it.

WHEN the key is dead or the reply carries no content,
THEN the smoke SHALL fail instead of reporting success.

#### Scenario: 401 is loud and the key is never printed
Given a local endpoint answering 401 and a key in the environment,
When   the smoke runs against it,
Then   it exits non-zero naming `HTTP 401`, and the key's value appears in no output.
- **Test:** `tests/test_agent_web_reach.py::test_a_dead_key_fails_with_the_code_and_no_empty_success`

#### Scenario: an empty 200 is refused
Given a local endpoint answering 200 with no `data.markdown`,
When   the smoke runs against it,
Then   it exits non-zero and says the body carried no content.
- **Test:** `tests/test_agent_web_reach.py::test_an_empty_body_is_not_healthy`

#### Scenario: a real body succeeds within the budget
Given a local endpoint answering 200 with markdown,
When   the smoke runs with a budget,
Then   it reports the status, prints a bounded excerpt, states the key was never printed, and keeps no
       more markdown than the budget.
- **Test:** `tests/test_agent_web_reach.py::test_a_real_body_is_success_and_the_key_is_never_shown`

#### Scenario: a missing key exits 2 and the opt-out says so
Given no key in the environment,
When   the smoke runs,
Then   it exits 2 naming `FIRECRAWL_API_KEY`, and `--allow-unconfigured` reports `NOT CONFIGURED` and
       appears in no workflow.
- **Test:** `tests/test_agent_web_reach.py::test_a_missing_key_is_loud_and_names_the_variable`
