# engine-bump-regen-is-real

## ADDED Requirements

### Requirement: The bump test reads the Dockerfile make writes

The fixture's `make generate-engine-params` MUST call `write_params`. The test
MUST read `containers/engines/dockerfiles/<id>/Dockerfile.cuda` and
`containers/engines/params/<id>.json` from that run. A target of `@true` does
not satisfy this.

#### Scenario: the fixture bump writes the apt package into the Dockerfile

- **Given** the fixture tags `v1.2.0` and `v1.3.0`
- **When** `bump` runs and its Makefile calls `write_params`
- **Then** `Dockerfile.cuda` written in the checkout contains `libnew1` on an `apt-get install` line
- **And** the params JSON install steps do not name `new-pkg`
- **And** the checkout HEAD is unchanged
- **Test:** `tests/test_engine_bump.py::test_bump_applies_one_fixture_before_it_commits`

### Requirement: A removal-only pin is reported

When the new tag only removes Python packages, `bump` MUST print
`python_removed` on the `DEPS` line. It MUST NOT invent a pip line and MUST
NOT commit.

#### Scenario: the v1.0.7 pyproject names leave the file

- **Given** the old tag's `pyproject.toml` depends on `huggingface-hub`, `jinja2`, `mlx`, `mlx-lm`, `numpy`, `safetensors`, and `tokenizers`
- **And** the new tag's `pyproject.toml` has an empty dependency list
- **When** `bump` runs
- **Then** the `DEPS` line contains `python_removed=huggingface-hub,jinja2,mlx,mlx-lm,numpy,safetensors,tokenizers`
- **And** `hard_fail` is empty
- **And** the install text is unchanged
- **Test:** `tests/test_engine_bump.py::test_bump_reports_packages_the_new_tag_removed`
