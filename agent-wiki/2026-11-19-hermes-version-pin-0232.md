# 2026-11-19 — Hermes pinned to v0.23.2 in the agent image (issue #2932)

Implements issue #2932 (OpenSpec change `hermes-version-pin-0232`): the agent image stops
floating on install.sh's `stable` channel and pins the Hermes CLI to exactly v0.23.2.

## What was verified against the spec

- **Dockerfile pin** — `containers/agent/Dockerfile` now declares
  `ARG HERMES_VERSION="0.23.2"` and `ARG HERMES_INSTALL_COMMIT="ae2a81ccc00e9b7c06301523e5bb09608397149c"`
  (the peeled v0.23.2 tag commit), forwards the `--commit ${HERMES_INSTALL_COMMIT}` flag through
  `HERMES_INSTALL_ARGS` (install.sh's `--commit` short-circuits channel selection), and carries
  `HERMES_VERSION` through the ENV block to the install step.
- **Read-back** — `scripts/install_hermes_ci.sh` adds a `VERSION` default and, after install, runs
  `hermes --version` and fails the build unless the first version token equals the pinned version —
  the same read-back discipline the skills-dir registration already uses.
- **Referee** — `scripts/agent_model_pin.py` (the existing check-agent-model gate, issue #405)
  declares `HERMES_VERSION` / `HERMES_INSTALL_COMMIT` once and its `check`/`report` now compare the
  Dockerfile ARGs, the install script's `VERSION` default, and the `--commit` forward, so drift in
  any home reddens the wired gate.
- **Proven** — `make check-agent-model` exits 0; `python3 -m pytest tests/test_agent_model_pin.py`
  → 14 passed (incl. `-k version` = 3, `-k drift` = 3); `tests/test_agent_image_refresh.py` → 6
  passed; `make openspec-tasks-check NAME=hermes-version-pin-0232` OK.

## Key decisions

- **The `0.19.0` serde strings stay.** `mk/tests.mk:35 HERMES_AGENT_PIN := hermes-agent==0.19.0`,
  `scripts/scan_agents_md.py:36` and `tests/fixtures/unit-suite.json` describe the pip-installed
  agents-read-venv guard (PyPI-capped at 0.19.0), not the image — the issue names this explicitly
  as out of scope, so they are untouched.
- **install.sh's `--commit`, not a post-install pip/uv pin.** `pip`/`uv` cannot deliver 0.23.x
  (PyPI stops at 0.19.0); the image's Hermes must come from install.sh, so the pin rides install.sh's
  own `--commit` flag and the referee verifies that flag is forwarded.
