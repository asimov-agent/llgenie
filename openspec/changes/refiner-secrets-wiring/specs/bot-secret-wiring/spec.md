# bot-secret-wiring

## ADDED Requirements

### Requirement: a workflow never reads a secret the repo does not define

Every `secrets.X` referenced in `.github/workflows/*.yml` SHALL exist in the repository's secret
list. A secret that is absent from `gh secret list` SHALL NOT be read by any workflow, because
GitHub substitutes an empty string for a missing secret and the job then runs with a blank value
instead of failing at the point of use.

#### Scenario: the refiner's refine job carries only defined keys

- **GIVEN** the `refine` job's `env:` block in `.github/workflows/issue-refiner.yml`,
- **WHEN** it is read,
- **THEN** it sets `NOUS_API_KEY` and `TYPESAFE_API_KEY` only, and names neither
  `OPENROUTER_API_KEY` nor `OPENCODE_API_KEY`.

- **Test:** `tests/test_issue_refiner.py::test_the_refine_job_does_not_read_undefined_secrets`

#### Scenario: no workflow in the tree reads an undefined secret

- **GIVEN** every `*.yml` under `.github/workflows/`,
- **WHEN** each `secrets.<NAME>` reference is collected,
- **THEN** none of them is `OPENROUTER_API_KEY` or `OPENCODE_API_KEY`.

- **Test:** `tests/test_workflow_guards.py::test_no_workflow_reads_an_undefined_secret`

### Requirement: the JEV preflight names the provider it actually uses

`scripts/agent_jev_preflight.sh` SHALL map the provider to its key variable for the providers the
repo configures. `HERMES_NERVE_PROVIDER` SHALL accept `typesafe`; any other value SHALL be refused
loudly with the list of supported providers. The preflight SHALL NOT name a provider the repo does
not configure.

#### Scenario: an unsupported provider is refused loudly

- **GIVEN** `HERMES_NERVE_PROVIDER` set to `openrouter`,
- **WHEN** the preflight runs,
- **THEN** it exits non-zero and its message names `typesafe` as the supported provider.

- **Test:** `tests/test_agent_nerve.py::test_an_unsupported_provider_is_refused_loudly`

#### Scenario: the typesafe provider selects TYPESAFE_API_KEY

- **GIVEN** `HERMES_NERVE_PROVIDER=typesafe`,
- **WHEN** the preflight's provider case runs,
- **THEN** the key variable it checks is `TYPESAFE_API_KEY`.

- **Test:** `tests/test_agent_nerve.py::test_the_typesafe_provider_selects_its_key`

### Requirement: the image build refuses a provider key in the build environment

The build SHALL refuse to continue when a provider key in the provider-key namespace
(`TYPESAFE_API_KEY`, `OPENROUTER_API_KEY`, `OPENCODE_API_KEY`) is present in the build environment,
so a token can never be baked into an image layer. This is a defence over the whole provider-key
namespace, not a wiring reference: it SHALL keep naming all three so a future provider key is caught
by the same guard.

#### Scenario: a provider key in the build environment fails the build

- **GIVEN** the build-time check in `containers/agent/Dockerfile` and
  `scripts/install_nerve_ci.sh`,
- **WHEN** any provider key is set in the build environment,
- **THEN** the build fails loudly and names the offending variable.

- **Test:** `tests/test_agent_nerve.py::test_a_provider_key_in_the_build_environment_fails_the_build`

### Requirement: the secret-output guard scans only variables the repo uses

`scripts/check_secret_output.py` SHALL list exactly the variables that carry a credential in this
repo. A variable the repo does not define SHALL NOT be in the list. The guard SHALL still fail on a
printed value for every variable that remains.

#### Scenario: the secret-output list drops the unused provider keys

- **GIVEN** `SECRET_VARS` in `scripts/check_secret_output.py`,
- **WHEN** it is read,
- **THEN** it contains `TYPESAFE_API_KEY` and not `OPENROUTER_API_KEY` or `OPENCODE_API_KEY`.

- **Test:** `tests/test_secret_output.py::test_the_secret_list_matches_the_repo_secrets`

### Requirement: the agent recipes pass only defined keys into the container

The agent `docker run` recipes in the `Makefile` SHALL pass only environment variables the repo
defines. A recipe SHALL NOT forward `OPENROUTER_API_KEY` or `OPENCODE_API_KEY`.

#### Scenario: the agent recipes carry only defined keys

- **GIVEN** the `issue-refiner`, `rebase-bot-agent`, `agent-jev-preflight` and `implement-issue`
  recipes in the `Makefile`,
- **WHEN** each is read,
- **THEN** it forwards `TYPESAFE_API_KEY` and does not forward `OPENROUTER_API_KEY` or
  `OPENCODE_API_KEY`.

- **Test:** `tests/test_issue_refiner.py::test_the_refiner_recipe_forwards_only_defined_keys`
