# Tasks: hermes-version-pin

- [x] Task 1: `containers/agent/Dockerfile` — add `ARG HERMES_VERSION="0.23.2"` and
      `ARG HERMES_INSTALL_COMMIT="ae2a81ccc00e9b7c06301523e5bb09608397149c"`, extend
      `HERMES_INSTALL_ARGS` with `--commit ${HERMES_INSTALL_COMMIT}`, forward `HERMES_VERSION`
      through the ENV block, and extend the HERMES_INSTALL_ARGS comment to name the pin.
- [x] Task 2: `scripts/install_hermes_ci.sh` — declare `HERMES_VERSION="${HERMES_VERSION:-0.23.2}"`,
      add the post-install `hermes --version` read-back assert (first version token must equal the
      pin; drift exits non-zero naming both values).
- [x] Task 3: `scripts/agent_model_pin.py` — declare `HERMES_VERSION` / `HERMES_INSTALL_COMMIT`
      constants, parse the Dockerfile ARGs + HERMES_INSTALL_ARGS `--commit ${HERMES_INSTALL_COMMIT}`
      + the install script's HERMES_VERSION default and the read-back assert; add the findings to
      the existing `check`/`report`.
- [x] Task 4: `tests/test_agent_model_pin.py` — add version/sha tests: committed tree is green,
      drifted version reddens naming file+value, drifted commit reddens, missing read-back assert
      reddens.
- [x] Task 5: agent-wiki entry `2026-11-19-hermes-version-pin.md` naming issue #2932 and the PR.
- [x] Task 6: gates green on the branch: `make check-agent-model`, `make lint`,
      `make check-wiring`, `make openspec-tasks-check`, `make lane-preflight`, `make test-unit`.
- [x] Task 7: push `feat/hermes-version-pin` and open the PR closing #2932; report the PR URL and
      stop for CI auto-merge.
