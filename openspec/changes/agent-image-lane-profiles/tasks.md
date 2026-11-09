# Tasks

- [x] 1. `scripts/agent_lanes_check.py`: a hermetic gate that reads `agents/manifest.json` against the profiles directory the build installed lanes into, and returns non-zero naming every declared lane whose home (`<profiles>/<name>/SOUL.md`) is absent — never a silent pass
- [x] 2. `containers/agent/Dockerfile`: COPY the `agents/` tree to `/opt/llgenie/agents` (+ `COPY agent_lanes_check.py /usr/local/bin/`), then a build `RUN` that installs each manifest-declared lane into `${HERMES_HOME}/profiles/<name>/` and runs `agent_lanes_check.py --agents /opt/llgenie/agents --profiles "${HERMES_HOME}/profiles"` so a missing lane FAILS the build
- [x] 3. `scripts/ci_images.py`: add `agents` (the whole lane tree) and `scripts/agent_lanes_check.py` to the agent image's hash inputs, and make `context()` place the agents tree under `agents/` preserving subpaths so the Dockerfile `COPY agents` resolves
- [x] 4. `tests/test_agent_lanes_check.py` in `make test-unit`: drive the real gate against fixture trees — a missing lane reds the build naming it, a complete install passes, a missing manifest reds loudly, a non-directory aborts
- [x] 5. `tests/test_ci_images.py`: the agent tag moves when a lane profile changes, and the build context carries the agents tree under `agents/`
- [x] 6. `scripts/package-layers.json`: register `agent_lanes_check` (Structural gates)
- [x] 7. Note trio for `agent-wiki/2026-11-08-agent-image-lane-profiles.md`, a `docs/changes.d/2026-11-08-agent-image-lane-profiles.md` row, and the regenerated `CHANGES.md`
- [x] 8. Verification: `make check-package-layers`, `make check-import-roots ratchet`, `make check-docs`, `make openspec-validate NAME=agent-image-lane-profiles`, `make openspec-tasks-check`, the hermetic unit suite, and the failed-build proof (`agent_lanes_check.py` against a manifest lane missing from the profiles dir → rc 1)
