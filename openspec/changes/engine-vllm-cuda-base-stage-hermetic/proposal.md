# engine-vllm-cuda-base-stage-hermetic

## Why

Issue #1832 surfaced a vllm-cuda producer failure: `make build-engine ENGINE=vllm ARCH=cuda`
failed, reddening every engine=vllm producer and blocking the #1696 runtime bind. The underlying
defect was a cross-invocation base pull: on the docker-container buildx driver a base left by a
PREVIOUS buildx invocation is never resolvable by a later `FROM <base>` (run 41971301136 @
84e9684ca2), so a bare `llgenie/base-cuda:<sha>` was pulled from docker.io and denied with
`insufficient_scope`. Issue #1753 fixed that in production code (`_combine_base_stage` builds the
backend base as an internal stage), but the fix was **unprotected** — no test locked the
conversion, so a future param/Dockerfile change could silently reintroduce the registry pull and
rebuild the same red.

## What changes

A regression-test guard only (the production fix is already landed in `_combine_base_stage`, issue
#1753):

- `tests/test_engine_image_matrix.py` gains `test_combine_base_stage_removes_cross_invocation_base_pull`,
  which sweeps every REAL derived engine Dockerfile and asserts that merging the backend base stage
  leaves **no** bare base `FROM` and no `docker.io` reference — a cross-invocation pull cannot come
  back unseen.
- `test_vllm_cuda_dockerfile_base_stage_is_hermetic` pins the specific vllm/cuda cell: its base
  resolves as the `llgenie-base` internal stage, never a registry pull.

No product code, workflow, or params change; no gate weakened.

## Out of scope

The producer's own concurrency queue (`engine-build-push`, #917) and the trigger concurrency key
(#1831) are separate issues. The actual build re-verification of the anchor run (42159549121 /
127701755058) is tracked at the issue, whose post-fix cuda log is still locked behind the in-progress
rocm cell.
