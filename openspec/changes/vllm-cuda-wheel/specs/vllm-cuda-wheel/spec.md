# vllm-cuda-wheel

## MODIFIED Requirements

### Requirement: the vLLM cuda cell is a THIN image over vLLM's official CUDA serving base, not a source compile

The `vllm` skill's `container.cuda` MUST declare `base: docker.io/vllm/vllm-openai:v0.33.0` with
`prebuilt: true`, and the generated `Dockerfile.cuda` MUST be only `FROM
docker.io/vllm/vllm-openai:v0.33.0` plus the llgenie entrypoint/healthcheck wrap with `install: []`
(zero install steps). The cuda install MUST NOT run `git clone`, `-e .`, `-r …/build/cuda.txt`,
`build_rust.sh`, or any wheel-install chain. The served version is the base's baked vllm, probed by
`detect` via `from vllm import __version__`. The `install.rocm` and `install.cpu` flows are unchanged.

#### Scenario: the generated cuda cell is a thin prebuilt image with zero install steps

Given the regenerated `containers/engines/params/vllm.json` cuda variant,
When  the source-build guard and the params read it,
Then  `prebuilt` is true, `install` is `[]` (0 steps), and it contains NO `git clone`, NO `-e .`,
NO `requirements/build/cuda.txt`, NO `build_rust.sh`, and NO wheel/curl install chain; the
generated `Dockerfile.cuda` is `FROM docker.io/vllm/vllm-openai:v0.33.0` + the entrypoint wrap.

- **Test:** `tests/test_engine_image_matrix.py` (`test_vllm_cuda_dockerfile_base_stage_is_hermetic`)
  and `tests/test_engine_skills.py` (`test_vllm_cuda_is_thin_prebuilt_not_a_wheel_install`) and
  `scripts/engine_source_guard.py check` (vllm/cuda is a tracked KNOWN_NOT_SOURCE cell).

#### Scenario: cuda is thin AND bypasses the internal base stage (an external docker.io pull)

Given the vllm cuda cell is `prebuilt: true` over an external official image,
When  `make build-engine ENGINE=vllm ARCH=cuda` runs,
Then  the Dockerfile's bare `FROM docker.io/vllm/vllm-openai:v0.33.0` is kept as a registry pull
(the thin cell is exempt from the internal-base-stage merge, mirroring sglang/cuda + tensorrt-llm/cuda),
with no `git clone`, no `-e .`, no `build_rust.sh`, no wheel-install chain in the cell.

- **Test:** `tests/test_engine_image_matrix.py` (thin prebuilt cells keep their official `FROM`).

#### Scenario: rocm and cpu still source-compile the pin

Given the regenerated rocm and cpu variants,
When  the params are read,
Then  their install steps still contain the pinned `git clone` and the `-e .` build for that
backend, with `prebuilt: false`.

- **Test:** `tests/test_engine_skills.py` (rocm/cpu install still carries the source build).
