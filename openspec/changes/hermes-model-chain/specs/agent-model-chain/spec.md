# agent-model-chain

## ADDED Requirements

### Requirement: The model chain has ONE home

The repository SHALL carry exactly one Hermes base model config, `agents/hermes-base-config.yaml`.
Its `model.default` SHALL be the real catalog id `meituan/longcat-2.5:free` — never an alias name,
because Hermes profile mode sends `model.default` verbatim to the endpoint and an alias there 404s
(measured against Hermes 0.23.2). The `model` block SHALL carry the route the endpoint needs at its
own level (`provider: custom`, the Nous OpenAI-compatible `base_url`, `key_env: NOUS_API_KEY`,
`max_tokens: 16000`), SHALL name the six aliases `nous-longcat`, `nous-hy4`, `nous-step`,
`nous-qwen4max`, `nous-solar`, `nous-deepseek` as bindings to catalog ids, and its
`fallback_providers` chain SHALL repeat the full route shape (`provider: custom` + `base_url` +
`key_env`) in order: `tencent/hy4-flash:free`, `stepfun/step-3.7-flash:free`, `qwen/qwen4-max:free`,
`upstage/solar-mini4:free`, and LAST `deepseek/deepseek-v4-flash-0731` — a fallback entry naming a
provider preset instead of the route never hops (measured). Every alias SHALL carry its
catalog-published `context_window` and the deliberate 16000-token `max_tokens` reply budget.

WHEN `make check-agent-model` reads the base config
THEN the chain SHALL match that order exactly, the last entry SHALL be `deepseek/deepseek-v4-flash-0731`,
every route the chain names SHALL carry `provider`, `base_url` and `key_env`, and any drift SHALL
exit non-zero naming the position it differs at.

#### Scenario: the committed chain is the declared chain

Given the repository as committed
When `make check-agent-model` runs
Then it prints the six-member chain (longcat first, deepseek-v4-flash-0731 last) and exits zero.

- **Test:** `tests/test_agent_model_pin.py::test_the_committed_chain_is_the_declared_chain`

#### Scenario: an alias in the default slot is a finding

Given a base config whose `model.default` names an alias instead of a catalog model id
When the checker runs against that tree
Then it exits non-zero: profile mode 404s on an alias sent to the endpoint.

- **Test:** `tests/test_agent_model_pin.py::test_an_alias_in_the_default_slot_is_a_finding`

#### Scenario: a route without base_url/key_env is a finding

Given a fallback entry that names `provider: nous` with no `base_url`/`key_env`
When the checker runs against that tree
Then it exits non-zero naming the entry and the keys it lacks — preset-shaped fallbacks never hop.

- **Test:** `tests/test_agent_model_pin.py::test_a_fallback_entry_without_its_custom_route_is_a_finding`

#### Scenario: a swapped fallback order is a finding, not a detail

Given a base config whose chain puts `tencent/hy4-flash:free` after `qwen/qwen4-max:free`
When the checker runs against that tree
Then it exits non-zero naming the swapped position.

- **Test:** `tests/test_agent_model_pin.py::test_a_swapped_fallback_order_is_a_finding`

#### Scenario: the last-resort model is not first

Given a base config whose `model.default` is the alias bound to `deepseek/deepseek-v4-flash-0731`
When the checker runs
Then it exits non-zero: the paid snapshot may only answer last.

- **Test:** `tests/test_agent_model_pin.py::test_the_paid_snapshot_leading_the_chain_is_a_finding`

### Requirement: Profiles own the model config; bots carry no model flag

No bot invocation SHALL set a model on the command line. `nous-alias := -m nous-deepseek` SHALL NOT
exist, and every Hermes bot call SHALL run as its lane profile (`hermes -p llgenie-<lane>`), which
loads its model chain from its own `config.yaml`. The base config SHALL be applied to EVERY llgenie
profile identically.

WHEN `grep -rn 'nous-alias' Makefile mk/` runs against the tree
THEN it SHALL print no lines, and the checker SHALL exit non-zero if any `-m nous` bot flag returns.

#### Scenario: no Makefile variable sets the model

Given the repository as committed
When the checker reads the Makefile and `mk/*.mk`
Then no `nous-alias` definition or use exists, and every bot recipe names its lane profile.

- **Test:** `tests/test_agent_model_pin.py::test_no_bot_invocation_sets_a_model`

#### Scenario: the fix-loop agent runs as the implementer lane

Given `scripts/fix_loop.sh`'s AGENT_CMD
When it is read
Then it runs `hermes -p llgenie-issse-implementer` and carries no `-m` flag.

- **Test:** `tests/test_fix_loop.py` (the agent-command shape assertions)

### Requirement: Every profile's config is installed from the base

`scripts/apply_hermes_base_config.py` SHALL merge the base config's owned keys — the whole
`model` route block (`default`, `provider`, `base_url`, `key_env`, `max_tokens`, `context_window`),
the `aliases`, and `fallback_providers` — into a Hermes home config and into each lane profile's
`config.yaml`, preserving keys the base does not own. `scripts/install_hermes_ci.sh` SHALL install the
base into the image's global home, `scripts/provision_agent_profiles.py` SHALL write every lane
profile's `config.yaml` from the base (host and image share the one code path), and the host
`make provision-agent-profiles` / `make sync-agent-profile` SHALL land the same chain per profile.

#### Scenario: a provisioned profile carries the chain

Given a fresh Hermes home provisioned by `scripts/provision_agent_profiles.py`
When any lane profile's `config.yaml` is read
Then its `model.default` is `meituan/longcat-2.5:free`, its aliases equal the base's, and its
`fallback_providers` equal the base chain in order.

- **Test:** `tests/test_agent_profiles.py` (provision writes the base chain into every lane profile config)

#### Scenario: a profile key the base does not own survives the merge

Given a profile config carrying an unrelated key
When the base config is applied to it
Then the unrelated key is preserved and the owned keys are replaced.

- **Test:** `tests/test_agent_profiles.py` (apply preserves non-owned keys)

### Requirement: The image build asserts the chain

The agent image SHALL bake the base config and SHALL fail its build unless the installed chain equals
the base: primary `nous-longcat` with `meituan/longcat-2.5:free`, the five fallbacks in order, every
alias carrying `model`, `max_tokens 16000` and its `context_window`, and each installed lane profile's
config carrying the same chain. The single-pin `HERMES_MODEL_ID`/`HERMES_ALIAS` ARGs SHALL NOT exist.

#### Scenario: a wrong chain fails the build

Given a Dockerfile whose inline chain assert is fed a config with the chain truncated
When the build-time assert runs
Then it exits non-zero naming the missing position.

- **Test:** `tests/test_agent_model_pin.py` (chain-assert wiring assertions) + the Dockerfile build RUN

#### Scenario: a profile whose chain differs fails the lane check

Given an installed profile config whose `fallback_providers` diverge from the base
When `scripts/agent_lanes_check.py` runs at image build
Then it refuses the image naming the profile.

- **Test:** `tests/test_agent_profiles.py` (lanes-check chain identity)

### Requirement: The smoke proves profile-resolved routing

`scripts/hermes_smoke.py` SHALL make its live call as a lane profile (`--profile`, default
`llgenie-status-keeper`) with no `-m` flag, proving Hermes routes through the profile's chain.

#### Scenario: the smoke call names no alias

Given the smoke script's argv builder
When it is read
Then it passes `-p <profile>` and never `-m`.

- **Test:** `tests/test_hermes_smoke.py` (argv assertions)

#### Scenario: the smoke audit judges the profile's own store

Given a profile run (measured against Hermes 0.23.2: `hermes -p <lane>` gets the profile home as
its Hermes home, so its session lands in `$HERMES_HOME/profiles/<lane>/state.db`)
When the smoke audits the transcript
Then it reads the profile home's `state.db` when that home exists, the global store otherwise,
and never fabricates a path for a lane whose home is missing.

- **Test:** `tests/test_hermes_smoke.py` (`test_a_profile_run_is_audited_in_the_profile_home`)

### Requirement: The chain's secret lands where profile mode reads it

`model.key_env` in profile mode names a variable the PROFILE's own `.env` must carry (measured
against Hermes 0.23.2: a key only exported into the leg's process environment authenticates
nothing). The agent image SHALL seed `NOUS_API_KEY` from the leg's process environment into the
global home's and every llgenie profile's `.env` at leg start — a `/etc/profile.d` hook because
every agent leg boots `bash -lc` — via `scripts/seed_profile_hermes_env.py`, staged into the image
build context like every other seam script. The host SHALL reach the same script through
`make seed-hermes-profile-env` (`--lanes`: the interactive default home's own `.env` is never
touched). The seeding SHALL never invent a value, never print one, never duplicate a key line,
never touch foreign profiles, and SHALL be a loud no-op — not a failure — when the environment
carries no key. The referee SHALL list the script among the seams the Dockerfile must wire.

WHEN a lane profile boots an agent leg in the published image
THEN `hermes -p llgenie-<lane>` resolves its chain's `key_env` from the seeded profile `.env` and
the model call authenticates against the named endpoint.

#### Scenario: seeding is idempotent and value-blind

Given profiles and a global home, and a key in the caller's environment
When `scripts/seed_profile_hermes_env.py` runs twice
Then each `.env` carries exactly one `NOUS_API_KEY=` line at mode 0600, foreign lines survive, no
output ever contains the value, and foreign profile homes stay untouched.

- **Test:** `tests/test_seed_profile_hermes_env.py`

#### Scenario: a Dockerfile that stopped seeding the profiles is a finding

Given a tree whose Dockerfile no longer stages/installs `seed_profile_hermes_env.py`
When `make check-agent-model` inspects the image seam list
Then it exits non-zero naming the missing seed hook.

- **Test:** `tests/test_agent_model_pin.py` (Dockerfile seam assertions)
