# agent-image-finding-refresh

## ADDED Requirements

### Requirement: the test image ships the current docker CLI stage

`containers/test/Dockerfile` MUST copy the docker CLI and buildx plugin from the newest published `docker:<major>-cli` stage, not from a superseded one. The stage choice MUST be stated in the file so a reader can see which upstream binary the image inherits.

WHEN the test image is built
THEN the docker CLI inside it is the CLI of a published docker CLI stage whose version meets the `docker/cli` advisory floors.

#### Scenario: the CLI stage is 29-cli

- **Given** `containers/test/Dockerfile`
- **When** the two docker CLI COPY lines are read
- **Then** both stages are `docker:29-cli` and no `docker:27-cli` remains in the file
- **Test:** `tests/test_agent_image_refresh.py::test_test_image_docker_cli_is_current`

### Requirement: the test image refreshes its Python build toolchain

The test image MUST upgrade `pip`, `setuptools`, and `wheel` to mirror-latest before installing the locked dependency set, so the toolchain frozen into the base image at its build date does not survive into the published image.

WHEN the test image is built
THEN the Python build toolchain installed in it is the mirror-current one, not the base image's frozen one.

#### Scenario: the upgrade layer exists before the lock install

- **Given** `containers/test/Dockerfile`
- **When** the pip layers are read in order
- **Then** a `pip install --no-cache-dir --upgrade pip setuptools wheel` RUN precedes the locked-requirements RUN
- **Test:** `tests/test_agent_image_refresh.py::test_test_image_upgrades_build_toolchain`

### Requirement: the agent image upgrades the debs it inherits

The agent image's apt layer MUST run `apt-get upgrade` after `apt-get update` and before installing its own packages, so packages inherited from the base image are refreshed to what the security mirror holds current at build time.

WHEN the agent image is built
THEN no base-image deb is left at a version the mirror has already superseded with a fix.

#### Scenario: the apt layer upgrades before it installs

- **Given** `containers/agent/Dockerfile`
- **When** the runtime apt RUN is read
- **Then** `apt-get upgrade -y` appears between `apt-get update` and `apt-get install`
- **Test:** `tests/test_agent_image_refresh.py::test_agent_apt_layer_upgrades_inherited_debs`

### Requirement: the published agent image skips unused Hermes toolchains

The agent image MUST install Hermes with `--skip-browser --skip-computer-use` by default: no llgenie lane uses the agent-browser/Playwright or computer-use toolchains, and the Chromium they ship is an advisory stream the repo can neither fix nor audit. The choice MUST be a build arg (`HERMES_INSTALL_ARGS`) exported to the install script, which forwards it to upstream `install.sh`.

WHEN the agent image installs Hermes
THEN upstream `install.sh` receives the `HERMES_INSTALL_ARGS` flag list, and the published image contains neither the browser toolchain nor the computer-use stack.

#### Scenario: the Dockerfile defaults the skip flags and exports them

- **Given** `containers/agent/Dockerfile`
- **When** the Hermes install args are read
- **Then** `ARG HERMES_INSTALL_ARGS` defaults to `--skip-browser --skip-computer-use` and the `ENV` block exports `HERMES_INSTALL_ARGS`
- **Test:** `tests/test_agent_image_refresh.py::test_hermes_install_skips_unused_toolchains`

#### Scenario: the install script forwards the args

- **Given** `scripts/install_hermes_ci.sh`
- **When** the Hermes install command is read
- **Then** it pipes the installer into `bash -s --` with `${HERMES_INSTALL_ARGS:-}` expanded
- **Test:** `tests/test_agent_image_refresh.py::test_install_script_forwards_hermes_args`

### Requirement: the agent image stages every module its provisioning step imports

The agent image build MUST stage `scripts/check_agent_skills.py` into the image's bin dir beside the other profile modules: `check_agent_profiles.py` imports `frontmatter()` from it at import time, and the build-time provisioning step (`provision_agent_profiles.py`) imports it transitively. A provisioning step that dies with `ModuleNotFoundError` makes `publish-agent-image` unbuildable — and because that workflow is dispatch-only, the breakage sat on `main` unnoticed (issue #2836 caught it by rebuilding locally).

WHEN the agent image build runs the profile-provisioning step
THEN every module the provisioning chain imports at import time is present in the image.

#### Scenario: check_agent_skills.py is in the hashed inputs and the COPY list

- **Given** the agent entry of `scripts/ci_images.py` and `containers/agent/Dockerfile`
- **When** the agent image's staged inputs are read
- **Then** `scripts/check_agent_skills.py` is a hashed input AND the Dockerfile COPYs it to `/opt/llgenie/bin/check_agent_skills.py`
- **Test:** `tests/test_agent_image_refresh.py::test_agent_image_stages_profile_import_chain`

### Requirement: the fleet resolution proof demands only what Hermes can resolve

`provision_agent_profiles.py`'s resolution denominator MUST mirror Hermes' own skill loader, so the build-time proof demands exactly what the runtime can provide (measured against the Hermes CLI, issue #2836):

- hidden path components (`.archive/…` and any dot-directory) are skipped by Hermes' loader, so an archived tree is not carried fleet behaviour and the proof must not count it;
- a skill whose frontmatter `platforms:` list excludes the platform running the proof is hidden by design, not missing, and the proof must not demand it;
- the resolved identity of a skill is its frontmatter `name` (what Hermes' table shows), not its directory name.

The lane trees MUST additionally carry no two skills with the same identity on the proof platform: Hermes resolves duplicates by category-qualifying one label (`software-development/…`), which the table proof cannot match.

WHEN the agent image build resolves each lane's skills
THEN every demanded skill is one Hermes resolves on that platform, and no demanded pair comes from a hidden, other-platform, or identity-collided tree.

#### Scenario: archived and other-platform skills are not demanded

- **Given** a lane tree with a `.archive/` skill and a `platforms: [macos]` skill, proof running on Linux
- **Then** `tree_skill_names` carries neither
- **Test:** `tests/test_provision_agent_profiles.py::test_hidden_skill_trees_are_not_carried_behaviour`, `::test_platform_gated_skill_is_carried_only_on_a_matching_platform`

#### Scenario: identity is the frontmatter name

- **Given** the planner tree's `pi-delegate` directory declaring `name: pi`
- **Then** `tree_skill_names` names `pi`, not `pi-delegate`
- **Test:** `tests/test_provision_agent_profiles.py::test_tree_skill_names_reads_every_skill_the_lane_carries`

#### Scenario: no lane tree carries a duplicate identity

- **Given** every lane under `agents/`
- **Then** no two visible, platform-carried SKILL.md files share one identity
- **Test:** `tests/test_provision_agent_profiles.py::test_no_lane_tree_carries_the_same_skill_identity_twice`
