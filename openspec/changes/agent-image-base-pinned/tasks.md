# Tasks: agent-image-base-pinned

## 1. The Dockerfile no longer defaults to a mutable base

- [x] 1.1 Remove the `llgenie/test:latest` default from `ARG TEST_IMAGE` in `containers/agent/Dockerfile`; comment states why (issue #2617).

## 2. The shape is locked by a test

- [x] 2.1 `tests/test_ci_images.py::test_agent_dockerfile_has_no_latest_base_default` locks the no-default ARG line; `tests/test_ci_images.py` passes in full.

## 3. The scan proves the finding is gone

- [x] 3.1 `make security-scan TOOL=trivy` on the branch reports zero misconfig rows across all Dockerfiles.

## 4. Documentation pair

- [x] 4.1 `agent-wiki/2026-11-13-agent-image-base-pinned-2617.md` + `docs/changes.d/…` row; `make changes-index` regenerated; `make check-docs` rc=0.

## 5. Verification

- [x] 5.1 `make lint`, `make check-workflows`, `make check-wiring`, `make openspec-validate NAME=agent-image-base-pinned`, `make lane-preflight` all rc=0; a bare `docker build -f containers/agent/Dockerfile .` (no build-arg) exits non-zero.
