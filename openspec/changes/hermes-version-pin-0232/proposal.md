# Pin the agent image's Hermes to v0.23.2

## Why

The agent image installs the Hermes CLI through the official install.sh, but the build does not
name WHICH Hermes it gets. install.sh's default `stable` channel takes "the latest published
release" as of the build moment, so two identical llgenie commits can ship different Hermeses and
a build that receives an older/newer CLI goes green anyway. Measured 2026-11-19 the newest
published Hermes is v0.23.2; the 0.19.0-era serde strings in the repo describe the pip-installed
agents-read-venv guard, not the image — pip cannot deliver 0.23.x (PyPI stops at 0.19.0).

## What Changes

1. `containers/agent/Dockerfile` pins the install through install.sh's own `--commit` flag: a new
   `ARG HERMES_INSTALL_COMMIT="ae2a81ccc00e9b7c06301523e5bb09608397149c"` (the peeled v0.23.2 tag
   commit) joins `HERMES_INSTALL_ARGS`, so the checkout is exactly v0.23.2. A named
   `ARG HERMES_VERSION="0.23.2"` flows through the existing ENV block to the install step.
2. `scripts/install_hermes_ci.sh` asserts the installed CLI version after install: it runs
   `hermes --version` and fails the build unless the first version token equals the pinned
   `HERMES_VERSION` default — the same read-back discipline the skills-dir registration uses.
3. `scripts/agent_model_pin.py` (the existing check-agent-model gate) grows the version/sha
   comparison between the Dockerfile ARGs and the install script's default, so drift reddens an
   already-wired gate instead of shipping a surprise.

## Impact

Every agent image build gets a deterministic, named Hermes; a build that installs any other
version fails loudly at build time. The model-chain work (#2929) lands on a Hermes that carries the
fallback chain. The pip-installed `HERMES_AGENT_PIN := hermes-agent==0.19.0` venv is untouched —
that is the AGENTS.md guard reader, not the image.
