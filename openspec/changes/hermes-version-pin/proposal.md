# Proposal: hermes-version-pin

## Why

The agent image installs the Hermes CLI through the official install.sh, but the build does not
name WHICH Hermes it gets. install.sh's default `stable` channel takes "the latest published
release" as of the build moment: `containers/agent/Dockerfile:78` (`HERMES_INSTALL_ARGS=
"--skip-browser --skip-computer-use"`) carries no version pin, and `scripts/install_hermes_ci.sh`
asserts the alias registration and the skills-dir read-back but never the installed CLI version.
Measured 2026-11-19: the newest published Hermes is **v0.23.2** (published 2026-11-16), while
PyPI's `hermes-agent` stops at 0.19.0 — so pip cannot deliver the release line at all, and a
floating-version image is an untracked build input: two builds of the same llgenie commit can
ship different Hermeses, and both go green.

The model-chain work (issue #2929) depends on Hermes's `fallback_providers` machinery
(`hermes_cli/fallback_config.py`), which the 0.19.0-era wheel does not carry. The chain work
needs a named 0.23.x Hermes, and that Hermes must be reproducible.

## What Changes

- The Hermes install is pinned **through install.sh itself**: a new Dockerfile
  `ARG HERMES_INSTALL_COMMIT="ae2a81ccc00e9b7c06301523e5bb09608397149c"` (the peeled v0.23.2
  tag commit) joins `HERMES_INSTALL_ARGS` as install.sh's `--commit` flag — install.sh checks
  out exactly v0.23.2.
- `ARG HERMES_VERSION="0.23.2"` names the version and flows through the existing ENV block to
  the install step.
- `scripts/install_hermes_ci.sh` reads the installed CLI back: `hermes --version` must report
  the pinned version or the BUILD fails — the same read-back discipline the skills-dir
  registration already uses.
- `scripts/agent_model_pin.py` (the existing `check-agent-model` gate referee) grows the
  version/sha comparison between the Dockerfile ARGs and the install script's default. No new
  CI seam: the gate is already wired into the unit sequence.
- `mk/tests.mk` `HERMES_AGENT_PIN := hermes-agent==0.19.0` stays unchanged: that is the
  pip-installed agents-read-venv guard, capped by PyPI, not the image.

## Impact

- Affected specs: `agent-hermes-version-pin` (new capability)
- Affected code: `containers/agent/Dockerfile`, `scripts/install_hermes_ci.sh`,
  `scripts/agent_model_pin.py`, `tests/test_agent_model_pin.py`
- Related issues: #2932 (this change), #2929 (model chain — depends on a 0.23.x Hermes),
  #2836 (the HERMES_INSTALL_ARGS flag list this pin extends)
