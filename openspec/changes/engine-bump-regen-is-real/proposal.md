# Proposal: engine-bump-regen-is-real

Issue: #192

## Why

`test_bump_applies_one_fixture_before_it_commits` ran `bump()` against a
Makefile whose `generate-engine-params` target was `@true`. The Dockerfile
assertions called `render_dockerfile` afterwards. That is not the file the
bump writes before it commits.

The TensorFold bump to v1.0.7 removed seven Python packages. `python_removed`
was in the findings and the PR body did not mention them, because the `DEPS`
line is printed only when a package is added.

## What Changes

- The fixture Makefile runs `write_params`. The test reads the Dockerfile and
  params JSON that command writes.
- `bump` prints `python_removed` and `apt_removed` on the `DEPS` line when a
  pin only removes packages.
- A second fixture uses the seven package names the v1.0.7 pin removed.

## Out of scope

The TensorFold unit tests that still expect `uv tool install … git+`. Issue #170.

## Impact

`scripts/engine_bump.py`, `tests/test_engine_bump.py`, `AGENTS.md`, `README.md`.

`AGENTS.md` states the rule: the fixture `make generate-engine-params` runs `write_params` and the test reads the files it wrote. A `@true` target does not test the bump. A removal-only pin prints `python_removed` on the `DEPS` line.
