# engine-build-pins Delta

## ADDED Requirements

### Requirement: the CI hf downloader is provisioned from the lock through a make target

The engine-build workflow's tiny-test-model downloader step MUST run
`make hf-cli-install`, and `make hf-cli-install` MUST install the exact
`huggingface_hub==<version>` spec stated by `tools/requirements.in` — never a
floating `>=` spec and never an inline `uv tool install` in the workflow. The
compile inputs MUST NOT request the `[cli]` extra (current `huggingface_hub`
ships `hf` in the base package; the extra prints a warning and nothing else).

#### Scenario: the step resolves the pinned version, not the resolver's choice

- **Given** `tools/requirements.in` pinning `huggingface_hub==1.30.0`
- **When** `make hf-cli-install` runs (proved in a disposable `UV_TOOL_DIR`: rc=0, `hf --version` reports `1.30.0`, no `extra named cli` warning)
- **Then** the installed version is the pinned one and the workflow file contains no `uv tool install`
- **Test:** `tests/test_requirements_pins.py::test_the_ci_hf_downloader_installs_the_pinned_spec_through_make`

#### Scenario: the target fails loudly when the pin is gone

- **Given** a `tools/requirements.in` with no `^huggingface_hub==<digit>` requirement line
- **When** `make hf-cli-install` runs
- **Then** it prints `[hf-cli-install] tools/requirements.in pins no huggingface_hub==<version>` and exits non-zero
- **Test:** `tests/test_requirements_pins.py::test_the_ci_hf_downloader_installs_the_pinned_spec_through_make` locks the guard line in the recipe
