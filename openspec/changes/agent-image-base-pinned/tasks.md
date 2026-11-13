# Tasks

## containers/agent/Dockerfile

- [x] 1.1 `ARG TEST_IMAGE=llgenie/test:latest` becomes `ARG TEST_IMAGE` (no default), and the
      header comment states the arg is mandatory and every wired builder passes the hashed ref.

## tests/test_ci_images.py

- [x] 2.1 New lock test `test_agent_dockerfile_test_image_arg_has_no_default`: asserts the
      Dockerfile's `ARG TEST_IMAGE` line carries no `=` default and no `:latest` tag, next to the
      existing `test_publish_agent_pins_the_test_image_it_builds_from`.

## scripts/ci_images.py

- [x] 3.1 Unchanged (verification only): `build_args` still returns `--build-arg
      TEST_IMAGE=<ghcr hashed ref>` for agent builds; no code change required.

## Verification

- [x] 4.1 Targeted pytest `tests/test_ci_images.py` rc=0 (whole file, existing tests unchanged;
      the new lock passes against the edited Dockerfile and a re-added default reds it): proven —
      `41 passed in 6.74s` rc=0, and the lock reds (`1 failed`) when `ARG TEST_IMAGE=llgenie/test:latest`
      is re-added (2026-11-13).
- [x] 4.2 `make openspec-validate NAME=agent-image-base-pinned` rc=0: proven — `Change
      'agent-image-base-pinned' is valid` rc=0 (2026-11-13).
- [x] 4.3 The Dockerfile header / any user-facing doc that names the arg stays accurate; `make
      lint`, `make check-docs`, `make check-wiring` rc=0: proven — host lint linefeeds `LINT OK`;
      check-docs `ok (815 entries)`; check-wiring `OK 422 documents … 375 make targets`
      (2026-11-13).
- [x] 4.4 The bare-build empty-base guarantee holds statically and the trivy misconfig is removed:
      `FROM ${TEST_IMAGE}` resolves from the value of `ARG TEST_IMAGE` (no inline default), so a
      `docker build` without `--build-arg TEST_IMAGE` substitutes the empty string and Docker
      refuses it (`base name () should not be empty`) — no mutable `:latest` can be selected;
      `grep` confirms zero `:latest` references that any trivy `DS148/dockerfile-latest-tag`
      finding could flag on the agent Dockerfile. The live trivy re-scan and the replayable bare
      `docker build` rc are recorded in the PR body for CI (issue AC 1 and AC 3), proven 2026-11-13.
- [x] 4.5 `agent-wiki/2026-11-13-agent-image-base-pinned.md` entry naming issue #2617 and the PR;
      `docs/changes.d/2026-11-13-agent-image-base-pinned.md` index row; no README change needed
      (build-arg plumbing is not user-facing) (2026-11-13).
