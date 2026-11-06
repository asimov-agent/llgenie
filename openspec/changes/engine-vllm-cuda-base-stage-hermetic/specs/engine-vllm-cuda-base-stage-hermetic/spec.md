# engine-vllm-cuda-base-stage-hermetic

## ADDED Requirements

### Requirement: a derived engine Dockerfile never pulls its backend base from a registry

Scenario: a derived engine Dockerfile `FROM`s its backend toolchain base (`llgenie/base-<backend>:<sha>`).
When `_combine_base_stage` merges that base as an internal stage, the combined Dockerfile MUST contain
`FROM llgenie-base` for the derived stage, MUST alias the backend toolchain base exactly once
(`AS llgenie-base`), and MUST NOT contain either a bare `FROM llgenie/base-<backend>:<sha>` or any
`docker.io` reference. A buildx run on the docker-container driver can then resolve the base inside the
single build instead of falling through to a denied registry pull (issues #1753/#1832).

WHEN a real committed engine Dockerfile `FROM`s its backend base
AND `_combine_base_stage` is applied
THEN the combined Dockerfile has `FROM llgenie-base`, one `AS llgenie-base`, and no `docker.io` /
bare-base `FROM`.

#### Scenario: every real derived cell is hermetic after the base-stage merge

- **Given** the real per-arch Dockerfiles under `containers/engines/dockerfiles/*/`
- **When** each backend-base-`FROM` cell is merged with `_combine_base_stage`
- **Then** no combined Dockerfile contains a bare base `FROM` or a `docker.io` reference
- **Test:** `tests/test_engine_image_matrix.py::test_combine_base_stage_removes_cross_invocation_base_pull`

#### Scenario: the vllm cuda cell resolves its base as an internal stage

- **Given** `containers/engines/dockerfiles/vllm/Dockerfile.cuda` (= `FROM llgenie/base-cuda:<sha>`)
- **When** `_combine_base_stage("cuda", …)` runs
- **Then** the combined Dockerfile uses `FROM llgenie-base` with one `AS llgenie-base` and no `docker.io`
- **Test:** `tests/test_engine_image_matrix.py::test_vllm_cuda_dockerfile_base_stage_is_hermetic`
