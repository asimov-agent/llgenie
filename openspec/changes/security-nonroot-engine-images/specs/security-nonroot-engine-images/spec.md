# security-nonroot-engine-images

## ADDED Requirements

### Requirement: every generated engine and shared-base Dockerfile serves as a non-root user

Trivy's `DS-0002` misconfiguration ("Specify at least 1 USER command in Dockerfile
with non-root user as argument") MUST report zero findings on the repository's shipped
containers: every `containers/engines/base/Dockerfile.<backend>` and every generated
`containers/engines/dockerfiles/<id>/Dockerfile.<variant>` MUST end its final runtime
stage with a non-root `USER` directive (the established `USER 65532:65532`), and the
renderer MUST be the single source of that guarantee so `make check-engine-params`
stays green.

WHEN the repository's generated Dockerfiles and shared bases are read
THEN each of them declares the non-root user `USER 65532:65532` in its final stage, and
`make check-engine-params` (the renderer exactly reproduces each committed file) passes.

#### Scenario: every generated engine image serves as a non-root user

- **Given** the committed generated engine Dockerfiles (`containers/engines/dockerfiles/*/Dockerfile.*`)
- **And** the committed shared bases (`containers/engines/base/Dockerfile.<backend>`)
- **When** their final stages are read
- **Then** each declares `USER 65532:65532` before its `HEALTHCHECK`/`ENTRYPOINT`/`CMD`
- **Test:** `tests/test_engine_skills.py::test_every_generated_engine_dockerfile_declares_a_nonroot_user`

#### Scenario: the renderer still reproduces every committed Dockerfile

- **Given** the committed params and the committed Dockerfiles
- **When** `render_dockerfile` is asked for each variant
- **Then** the output equals the committed file byte-for-byte, and `make check-engine-params` exits 0
- **Test:** `tests/test_engine_skills.py::test_one_generated_dockerfile_per_engine_arch`

### Requirement: a base-using build stage still compiles as root, then web-serving drops to non-root

A cell built `FROM` the shared base (which ends in `USER 65532:65532`) MUST reset
`USER root` before its compile/install step, so `engine_runner.py install` keeps its
root privileges, and MUST re-drop to the non-root user in the final runtime stage so the
served engine is never root. A host-mounted read-only `/models` must not crash the
non-root `serve` path.

WHEN a compiled engine's Dockerfile is read
THEN its build stage carries `USER root` right after the shared-base `FROM`, its final
stage drops to `USER 65532:65532`, and the HF-cache `mkdir` tolerates an unwritable
`/models`.

#### Scenario: a compiled engine resets root for the build and serves non-root

- **Given** a compiled engine Dockerfile built on the shared base (e.g. `llama.cpp/cuda`)
- **When** its stages are read
- **Then** the stage `FROM ...base... AS build` is immediately followed by `USER root`, and the
  runtime stage ends with `USER 65532:65532` before `HEALTHCHECK`
- **Test:** `tests/test_engine_skills.py::test_compiled_engine_build_stage_resets_root_and_serves_nonroot`

#### Scenario: a read-only host-mounted /models never blocks non-root serving

- **Given** `engine_runner.py` `serve_plan` running with `HF_HOME` pointing at a read-only path
- **When** it reaches its HF-cache `mkdir`
- **Then** it proceeds without raising, so the engine still serves
- **Test:** `tests/test_engine_skills.py::test_engine_runner_hf_cache_mkdir_tolerates_read_only_models`

### Requirement: the test image defaults to a non-root user while the harness runs root

`containers/test/Dockerfile` MUST declare a non-root default `USER`, and every Makefile
test invocation MUST explicitly run the image as root (`-u root`) so the root-required
harness (rw repo mount, host docker socket, writing build artifacts) is unchanged.

WHEN the test Dockerfile and the Makefile test runners are read
THEN the image declares `USER 65532:65532` and `TEST_OPTS`, `ENGINE_TEST_ARGS` and
`CI_HOME_CLEAN` all pass `-u root`.

#### Scenario: the test image defaults to non-root and the harness overrides to root

- **Given** the real checkout
- **When** `containers/test/Dockerfile`, `TEST_OPTS`, `ENGINE_TEST_ARGS` and `CI_HOME_CLEAN` in the Makefile are read
- **Then** the image declares `USER 65532:65532` and every runner passes `-u root`
- **Test:** `tests/test_engine_skills.py::test_test_image_defaults_nonroot_and_harness_runs_root`
