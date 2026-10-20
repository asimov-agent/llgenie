# agent-web-reach

## MODIFIED Requirements

### Requirement: A bot leg reaches the masked fetch, and the URLs it depends on are checked

At least one bot leg SHALL pre-fetch the URLs an issue names with the ONE `make agent-fetch` leg before
the agent reviews, guarded by the agent-shell credential check, and the repository SHALL be able to
report whether the URLs the bots depend on resolve. A wiring assertion SHALL fail when no CI-reached
target calls `agent-fetch`.

WHEN a bot leg reviews an issue that names a URL
THEN the URL is pre-fetched by the masked leg and the agent reads the fetched text as evidence, or the
index records that it could not be read.

#### Scenario: the pre-fetch leg is reached by a bot run

Given the wiring graph of the workflow files and the Makefile's call graph,
When  the CI-reached targets are closed over the calls they make,
Then  `agent-fetch` is among them, reached through `issue-evidence` from the refiner leg.

- **Test:** `tests/test_agent_web_reach.py::test_a_bot_leg_reaches_agent_fetch`

#### Scenario: the credential is proven visible before anything is fetched

Given the refiner leg's recipe and the job that runs it,
When  the order of its steps is read,
Then  the agent-shell check for `FIRECRAWL_API_KEY` precedes the pre-fetch, and the key is forwarded by
      NAME only.

- **Test:** `tests/test_agent_web_reach.py::test_the_bot_leg_forwards_the_key_by_name_and_gates_first`

#### Scenario: an issue's URLs are extracted from its prose

Given an issue body that names URLs inside prose, repeats one, and wraps one in punctuation,
When  the candidates are extracted,
Then  each URL appears once, without trailing punctuation or a fragment, and a loopback URL is dropped.

- **Test:** `tests/test_agent_web_reach.py::test_the_candidates_are_extracted_from_prose`

#### Scenario: a dead URL fails the coverage check

Given a URL that answers 404,
When  `make web-coverage` checks it,
Then  the line reports the status and the command exits non-zero, naming the dead URL.

- **Test:** `tests/test_agent_web_reach.py::test_a_dead_url_is_reported_and_fails_the_coverage_check`
  (live: CI job `search-smoke.yml` → `make web-coverage`)

#### Scenario: a credential-gated URL is not a dead one

Given a URL that answers 403,
When  the coverage classifier is asked,
Then  it is not dead — the resource exists and wants a credential the bot does not have — while a 404,
      a 500 and a failed read are.

- **Test:** `tests/test_agent_web_reach.py::test_the_coverage_fixture_names_urls_and_gated_urls_are_not_dead`
