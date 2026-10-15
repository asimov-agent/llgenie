# agent-nerve-jev

## ADDED Requirements

### Requirement: the agent image carries the host's JEV layer, wired as the host wires it

The agent image MUST install the Nerve plugin at an immutable commit of `keeltrace/hermes-nerve` and
enable it, MUST write the plugin's documented settings under `plugins.entries.nerve.settings` (the
only path Hermes reads for a plugin's options), and MUST select the profile the host runs through the
sidecar `HERMES_HOME/nerve/profile.json` — written through the plugin's own profile writer, not by
hand. The build MUST fail when the ref is not a 40-character commit SHA, when a provider key is
present in the build environment, when the bundle did not land, when the plugin is not enabled, when
the profile is not one the plugin knows, or when a setting did not land where Hermes reads it.

WHEN the image is built THEN the plugin is enabled in its `HERMES_HOME`, the settings resolve from
`plugins.entries.nerve.settings`, and the plugin's own loader reports the profile.

#### Scenario: an immutable pin, and the settings Hermes actually reads

- **Given** the agent Dockerfile and the install script it runs
- **When** the pin and the settings are read
- **Then** the default ref is a 40-character commit SHA naming the release it came from, the
  Dockerfile carries the same pin, and every setting the host runs is written through the
  `plugins.entries.nerve.settings` path
- **And** the build asserts the layer instead of assuming it
- **Test:** `tests/test_agent_nerve.py::test_the_build_pins_the_release_commit_and_the_hosts_settings`
- **Test:** `tests/test_agent_nerve.py::test_the_build_requires_an_immutable_commit_pin`

#### Scenario: the documented nervous system, and the gate it does not replace

- **Given** a home and a CLI that behave like the real ones
- **When** the build half runs
- **Then** the config carries `nervous_enabled`, `nervous_turn_admission`, `nervous_mode`,
  `nervous_challenge_confidence`, `nervous_call_threshold`, `context_engine_mode` and
  `context_curation_mode` as documented, `gate_mode` stays the STRING `off`, and every one of them is
  read back by the script
- **Test:** `tests/test_agent_nerve.py::test_the_build_sets_the_documented_nervous_defaults`
- **Test:** `tests/test_agent_nerve.py::test_the_build_wires_the_hosts_settings_and_keeps_gate_mode_a_string`

#### Scenario: the profile decides which modules the settings tune

- **Given** a home with the plugin package and the CLI stand-in
- **When** the build half runs
- **Then** `HERMES_HOME/nerve/profile.json` exists in the plugin's own shape with the requested
  profile, the plugin's loader reports the same profile, and a profile the plugin does not know fails
  the build by name
- **Test:** `tests/test_agent_nerve.py::test_the_build_selects_the_hosts_profile_through_the_plugins_own_loader`
- **Test:** `tests/test_agent_nerve.py::test_the_build_refuses_a_profile_the_plugin_does_not_know`

#### Scenario: the dead pre-0.3.1 settings block is removed

- **Given** a base image whose config carries `plugins.entries.hermes-nerve` (never read by Hermes)
- **When** the build half runs
- **Then** the block is gone and the run says why
- **Test:** `tests/test_agent_nerve.py::test_the_build_removes_the_dead_pre_0_3_1_settings_block`

### Requirement: the provider key is never baked into the image

The build MUST refuse to continue when a provider key (`TYPESAFE_API_KEY`, `OPENROUTER_API_KEY`,
`OPENCODE_API_KEY`) is present in the build environment, and no file in the image's build context may
contain a key value or write the key with `ENV`. The key MUST reach the container only at run time
(`docker run -e`), exactly like `NOUS_API_KEY`.

WHEN the build environment carries a provider key THEN the build fails, naming the variable.

#### Scenario: a key in the build environment fails the build

- **Given** a build environment with `TYPESAFE_API_KEY` set
- **When** the install script runs
- **Then** it exits non-zero, naming the variable, and says the token must arrive at run time
- **Test:** `tests/test_agent_nerve.py::test_the_build_refuses_a_provider_key_in_the_build_environment`
- **Test:** `tests/test_agent_nerve.py::test_the_workflows_pass_the_key_at_run_time_only`

### Requirement: the JEV layer never stops a bot run

Before any agent work, `scripts/agent_jev_preflight.sh` MUST report whether the layer is available for
THIS run: the plugin bundle in this `HERMES_HOME`, the provider key (environment or the home's
`.env`), the plugin *enabled*, and a **real** provider decision call through the plugin's own live
smoke. Every one of those failures MUST be reported with the remedy and the run MUST CONTINUE with
exit 0, because the bots are autonomous and an unavailable decision layer only makes a run more
expensive and more mistake-prone — never stopped. `NERVE_REQUIRE=1` MUST turn the report into a
non-zero exit and MUST NOT be set by any bot workflow.

WHEN the layer is unavailable THEN the run proceeds, loudly.

#### Scenario: a missing key is reported, and the run continues

- **Given** a home with the plugin installed and no provider key
- **When** the preflight runs
- **Then** it exits 0, names `TYPESAFE_API_KEY` with both ways to supply it, says JEV is inactive for
  this run, and prints no key
- **Test:** `tests/test_agent_nerve.py::test_a_missing_provider_key_is_reported_and_the_run_continues`

#### Scenario: verification mode is the only way to fail

- **Given** the same key-less home and `NERVE_REQUIRE=1`
- **When** the preflight runs
- **Then** it exits non-zero and says the flag is why
- **Test:** `tests/test_agent_nerve.py::test_nerve_require_turns_the_report_into_a_failure`

#### Scenario: a home without the plugin, and a provider that does not answer

- **Given** a home with no plugin bundle, and separately a home whose provider smoke fails
- **When** the preflight runs
- **Then** both report the reason and the remedy and exit 0, and `NERVE_REQUIRE=1` turns each into a
  failure
- **Test:** `tests/test_agent_nerve.py::test_a_home_without_the_plugin_is_reported_and_the_run_continues`
- **Test:** `tests/test_agent_nerve.py::test_a_provider_that_does_not_answer_does_not_stop_the_run`

#### Scenario: autonomy is asserted, not assumed

- **Given** the two bot workflows
- **When** their environment is read
- **Then** neither sets `NERVE_REQUIRE` (no precondition) nor `ALLOW_UNSUPERVISED` (nothing to opt out
  of)
- **Test:** `tests/test_agent_nerve.py::test_no_bot_workflow_requires_the_layer_or_opts_out_of_it`

### Requirement: every bot path runs the preflight, and the key travels by name

`make agent-jev-preflight` MUST run inside the agent image as a working recipe, `make implement-issue`
MUST run the preflight before the Hermes call, `make fix-loop-image` MUST run it before the loop, and
each of those targets MUST pass the provider key into the container **by variable name**
(`-e TYPESAFE_API_KEY`), never by value. `issue-bot.yml` and `fix-bot.yml` MUST take the key from
`secrets.TYPESAFE_API_KEY`, and the issue-bot MUST run the preflight as a step before the implementer.

WHEN a bot target starts a container THEN the provider key is in its environment by name and the
preflight has already reported.

#### Scenario: the make targets are the only path in, and they carry the preflight

- **Given** the Makefile and the two bot workflows
- **When** each bot target's `docker run` and each workflow's wiring is read
- **Then** every target passes `-e TYPESAFE_API_KEY`, the implementer's internal recipe runs
  `_agent-jev-preflight` before `hermes -z`, the fix loop runs the preflight before
  `scripts/fix_loop.sh`, the public target runs `ensure` and a container, and both workflows wire
  `secrets.TYPESAFE_API_KEY`
- **Test:** `tests/test_agent_nerve.py::test_the_key_reaches_the_container_through_make_targets`
- **Test:** `tests/test_agent_nerve.py::test_the_workflows_pass_the_key_at_run_time_only`

### Requirement: the scripts are part of the image's identity and the repo's wiring

Both scripts MUST be COPYed by the Dockerfile **and** listed among the agent image's hash inputs in
`scripts/ci_images.py`, so a changed script moves the image tag a job resolves. The new test file MUST
be named by `make test-unit`, `agent-jev-preflight` MUST be declared `.PHONY` and documented in
`make help` and the README, and no file may still name the old gate script.

WHEN a script changes THEN the agent image's hash tag changes with it.

#### Scenario: the image tag moves with the scripts, and the target is documented

- **Given** the image registry, the Dockerfile, the Makefile and the README
- **When** the agent image's inputs and the target's documentation are read
- **Then** every COPYed script is a hash input, the test file is in `test-unit`, the target is in
  `.PHONY` and `make help`, the README documents the layer and says it never blocks a run, and the old
  script name appears nowhere
- **Test:** `tests/test_agent_nerve.py::test_a_changed_nerve_script_moves_the_agent_image_tag`
- **Test:** `tests/test_agent_nerve.py::test_the_preflight_is_documented_for_the_reader`
