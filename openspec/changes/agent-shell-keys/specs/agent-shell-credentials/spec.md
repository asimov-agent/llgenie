# agent-shell-credentials — spec delta

Capability: `agent-shell-credentials`
Issue: [#358](https://github.com/asimov-agent/llgenie/issues/358)

## ADDED Requirements

### Requirement: One list of agent-visible credentials

The Makefile SHALL define ONE list, `AGENT_SHELL_KEYS`, naming every credential a container
receives, and every agent leg SHALL forward each listed name as both `-e <NAME>` and
`-e _HERMES_FORCE_<NAME>` — by NAME only, never as `-e <NAME>=<value>`.

WHEN a bot leg starts the agent image with a credential,
THEN the command SHALL carry the plain name and the `_HERMES_FORCE_` twin, and the credential's VALUE
SHALL NOT appear on a command line, in a recipe or in any log.

#### Scenario: a leg forwards the forced twin, never the value
Given the Makefile's `AGENT_SHELL_KEYS` list and sentinel values in the environment,
When   `make -n` renders an agent leg's command,
Then   every listed key appears as `-e _HERMES_FORCE_<NAME>` and no sentinel value appears anywhere in
       the rendered text.
- **Test:** `tests/test_agent_shell_keys.py::test_the_forced_names_travel_by_name_never_by_value`

#### Scenario: a key a leg forwards is in the list
Given an agent leg's recipe that forwards `-e <NAME>`,
When   the wiring test resolves `AGENT_SHELL_KEYS` as make itself expands it,
Then   `<NAME>` (or the variable it is spelled through) is a member of that list, so no leg forwards a
       credential the agent's shell is not proven to see.
- **Test:** `tests/test_agent_shell_keys.py::test_the_list_names_every_credential_an_agent_leg_forwards`

### Requirement: `make` exports the forced twin from the plain name

On the HOST, the Makefile SHALL export `_HERMES_FORCE_<NAME>` from `<NAME>` by reference, and only
when `<NAME>` is set and non-empty. Inside a container the Makefile SHALL NOT re-create the forced
name, so that the check proves what `docker run` forwarded rather than what an inner `make` invented.

WHEN a recipe that reads `_HERMES_FORCE_<NAME>` runs on the host with `<NAME>` set,
THEN the forced name holds a value of the same length; WHEN `<NAME>` is unset, THEN the forced name is
empty and unexported; WHEN the same recipe runs inside a container, THEN nothing is re-created.

#### Scenario: the host exports, the container does not
Given a host whose `NOUS_API_KEY` is set and whose `FIRECRAWL_API_KEY` is unset,
When   a fixture target prints the length of each `_HERMES_FORCE_<NAME>`,
Then   the forced twin of the set key has that key's length, the forced twin of the unset key is
       empty, and with `IN_CONTAINER=1` (the `/.dockerenv` case) neither is re-created.
- **Test:** `tests/test_agent_shell_keys.py::test_make_exports_the_forced_name_from_the_plain_one`

### Requirement: the check reads the AGENT's real terminal environment

`scripts/agent_shell_keys_check.py` SHALL run its probe through Hermes's REAL terminal environment
(`LocalEnvironment`, the code the agent's `terminal` tool uses) and SHALL fail, naming the variable,
when a key that IS set in the container reads empty in the agent's shell. It SHALL print lengths only
— never a value, never a prefix, never a slice.

WHEN a credential is set in the container but stripped from the agent's shell,
THEN the check SHALL exit non-zero and name the variable and the fix.

#### Scenario: the plain name leaves the agent blind
Given the agent image with `NOUS_API_KEY` set and no `_HERMES_FORCE_NOUS_API_KEY`,
When   `make agent-shell-keys-check` runs,
Then   it exits non-zero (1), reports `NOUS_API_KEY: container=set agent-shell=EMPTY`, names the
       `_HERMES_FORCE_<NAME>` seam as the fix, and prints no value.
- **Test:** `CI steps in \`.github/workflows/{fix-bot,issue-bot,issue-refiner,rebase-bot}.yml\` ->
  \`make agent-shell-keys-check\`` (those steps run the probe against the real Hermes inside
  `llgenie/agent`; the hermetic half asserts the target is wired to them:
  `tests/test_agent_shell_keys.py::test_every_bot_job_proves_the_agent_shell`)

#### Scenario: the forced twin makes the key visible
Given the agent image with both `NOUS_API_KEY` and `_HERMES_FORCE_NOUS_API_KEY` set,
When   `make agent-shell-keys-check` runs,
Then   it exits zero and reports the key as `container=set agent-shell=set (match …)`.
- **Test:** `CI steps in \`.github/workflows/{fix-bot,issue-bot,issue-refiner,rebase-bot}.yml\` ->
  \`make agent-shell-keys-check\``

### Requirement: a missing credential is loud, never a skip

A key that is not set in the container, or a Hermes that cannot be found where the check runs, SHALL
be a LOUD failure (exit 2). `--allow-unconfigured` SHALL be the only opt-out, it SHALL say
`NOT CONFIGURED` in its output, and no workflow SHALL use it.

WHEN the container has no `NOUS_API_KEY`,
THEN the check SHALL exit 2 and name the variable (never a silent pass).

#### Scenario: unset key fails closed
Given an environment with no credential set,
When   the check runs with the default list,
Then   it exits 2, names the missing variable, and prints no value.
- **Test:** `tests/test_agent_shell_keys.py::test_a_missing_key_is_loud_and_the_opt_out_says_so`

#### Scenario: the opt-out never reaches CI
Given every file under `.github/workflows/`,
When   the wiring test greps for `agent-shell-keys` beside `allow-unconfigured`,
Then   no workflow pairs them.
- **Test:** `tests/test_agent_shell_keys.py::test_a_missing_key_is_loud_and_the_opt_out_says_so`

### Requirement: every bot job proves its credential reaches the agent

Each bot job that starts the agent image SHALL run `make agent-shell-keys-check` before its agent
work, and SHALL fail the job when a credential it forwards cannot reach the agent's shell.

WHEN a bot job starts,
THEN the step that proves the agent's shell is present, before the agent spends model time.

#### Scenario: the bot jobs carry the proof
Given `.github/workflows/fix-bot.yml`, `issue-bot.yml`, `issue-refiner.yml` and `rebase-bot.yml`,
When   the wiring test reads each file,
Then   each names `make agent-shell-keys-check` as a step.
- **Test:** `tests/test_agent_shell_keys.py::test_every_bot_job_proves_the_agent_shell`
