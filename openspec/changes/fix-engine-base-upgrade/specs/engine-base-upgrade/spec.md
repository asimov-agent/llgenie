# fix-engine-base-upgrade

## ADDED Requirements

### Requirement: the engine base image upgrades the debs it inherits

The shared engine base Dockerfile (`scripts/engine_skills.py::render_base_dockerfile`) MUST run `apt-get upgrade -y` after `apt-get update` and before installing its build toolchain, so packages inherited from the upstream base image (`nvidia/cuda:13.0.2-devel-ubuntu24.04`, `ubuntu:24.04`, `rocm/dev-ubuntu-24.04:7.0-complete`) are refreshed to what the security mirror holds current at build time instead of re-shipping the frozen set baked into the base (the 15 HIGH inherited findings on the llama-cpp CUDA image).

WHEN the base Dockerfile is rendered for a backend
THEN its apt `RUN` layer runs `apt-get upgrade -y` between `apt-get update` and the toolchain `apt-get install`, for every backend (cpu, cuda, rocm, vulkan).

#### Scenario: the base renderer emits the upgrade line for every backend

- **Given** `scripts/engine_skills.py::render_base_dockerfile`
- **When** it renders the base Dockerfile for each of cpu, cuda, rocm, vulkan
- **Then** every rendered base carries `apt-get update && apt-get upgrade -y` before the toolchain install
- **Test:** `tests/test_engine_base_upgrade.py::test_render_emits_upgrade_for_all_backends`

### Requirement: the generated base files stay in sync with the renderer

The base tag is the content hash of the rendered Dockerfile, so a renderer change MUST be propagated to the on-disk generated files: all four `containers/engines/base/Dockerfile.<backend>` change and every engine Dockerfile's build stage re-pins the new `llgenie/base-<backend>:<hash>` tag. `make check-engine-params` MUST report zero stale files.

WHEN the base renderer changes and `make generate-engine-params` has run
THEN the on-disk generated files match the renderer and `make check-engine-params` passes.

#### Scenario: generated base files and engine FROM lines are in sync

- **Given** the base renderer emits `apt-get upgrade -y`
- **When** `make generate-engine-params` has regenerated the files and `make check-engine-params` checks them
- **Then** all four base Dockerfiles carry the upgrade layer, every engine Dockerfile's build stage pins the matching new base tag, and `make check-engine-params` reports 0 stale files
- **Test:** `tests/test_engine_base_upgrade.py::test_generated_files_in_sync`, `tests/test_engine_base_upgrade.py::test_check_engine_params_green`
