# Hermes version pin: the agent image installs a named release (issue #2929 side, #2932)

Issue: #2932 · PR: #2933 (feat/hermes-version-pin → main) · OpenSpec change: `hermes-version-pin`

## What was built

- `containers/agent/Dockerfile` now declares `ARG HERMES_VERSION="0.23.2"` and
  `ARG HERMES_INSTALL_COMMIT="ae2a81ccc00e9b7c06301523e5bb09608397149c"` — the peeled commit of the
  upstream annotated tag v0.23.2 (tag object `28f57ed8e3dba4eceb67dfd3e3abda1a7604452d`; only the
  peeled commit is checkout-able by install.sh `--commit`). `HERMES_INSTALL_ARGS` carries
  `--commit ${HERMES_INSTALL_COMMIT}` next to the #2836 skip flags, and `HERMES_VERSION` is forwarded
  through the ENV block to the install step.
- `scripts/install_hermes_ci.sh` reads the installed CLI back: `hermes --version`'s first version
  token must equal the pin (a drift suffix like `0.23.1+6066` fails too), and the script exits
  non-zero naming both values otherwise.
- `scripts/agent_model_pin.py` (the existing `check-agent-model` referee) gained
  `HERMES_VERSION` / `HERMES_INSTALL_COMMIT` constants and `version_findings()`: Dockerfile version,
  Dockerfile commit, ARGS actually passing `--commit ${HERMES_INSTALL_COMMIT}`, the install script's
  `HERMES_VERSION` default, and the presence of the read-back assert. No new gate was registered —
  the extension rides the existing CI sequence step.

## Verified

- Measured on main `51de7d82c`: PyPI `hermes-agent` tops out at **0.19.0** while the GitHub release
  line is **v0.23.2** (published 2026-11-16T20:59:18Z) — the pin can only travel through install.sh,
  not `uv tool install hermes-agent`. install.sh honors `--commit SHA` (usage line 72, implementation
  ~lines 694/747) and skips channel resolution for it.
- Buildkit probe (local docker): a post-FROM `ARG` default CAN reference a post-FROM ARG
  (`--commit ${HERMES_INSTALL_COMMIT}` expands; a pre-FROM reference does not — the Dockerfile's
  Hermes ARG block sits after FROM, so the expansion holds).
- `make check-agent-model` → `OK` with the hermes line in the report;
  `pytest tests/test_agent_model_pin.py` → 15 passed (7 new version/drift tests);
  `make lint` OK; `make check-wiring` OK (no new scripts, no new seams).
- `HERMES_AGENT_PIN := hermes-agent==0.19.0` in `mk/tests.mk` stays unchanged: it pins the pip-only
  guard venv, a different home than the image install.

## Status

Branch `feat/hermes-version-pin`; PR targets #2932 and closes it. `make test-unit` +
`make lane-preflight` run on the branch before push.
