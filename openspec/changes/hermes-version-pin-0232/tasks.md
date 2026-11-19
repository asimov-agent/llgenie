# Tasks

- [x] 1. `containers/agent/Dockerfile`: add `ARG HERMES_VERSION="0.23.2"` and `ARG HERMES_INSTALL_COMMIT="ae2a81ccc00e9b7c06301523e5bb09608397149c"`, forward the `--commit` flag through `HERMES_INSTALL_ARGS`, and flow `HERMES_VERSION` through the ENV block
- [x] 2. `scripts/install_hermes_ci.sh`: add a `VERSION` default and, after install, run `hermes --version` and fail the build unless the first token equals the pinned version
- [x] 3. `scripts/agent_model_pin.py`: declare `HERMES_VERSION` / `HERMES_INSTALL_COMMIT` once and extend `check`/`report` with the version/sha comparison across the Dockerfile ARGs, the install script default, and the `--commit` forward
- [x] 4. `tests/test_agent_model_pin.py`: add version and drift tests (the committed pin is green; a drifted version in either file, a drifted commit, and a dropped `--commit` flag are each a finding)
- [x] 5. Verified for real: `make check-agent-model` exits 0; `python3 -m pytest tests/test_agent_model_pin.py -k version` and `-k drift` exit 0; `tests/test_agent_image_refresh.py` stays green
