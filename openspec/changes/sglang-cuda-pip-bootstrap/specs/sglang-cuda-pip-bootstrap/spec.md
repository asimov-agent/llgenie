# sglang-cuda-pip-bootstrap

## MODIFIED Requirements

### Requirement: sglang/cuda's install steps use the uv bootstrap, not the base's missing pip

The `sglang` skill's `install.cuda` MUST NOT call `python3 -m pip` on the shared
cuda build base (`llgenie/base-cuda`) — that image's system Python has no `pip`
module (`/usr/bin/python3: No module named pip`), which fails
`make build-engine ENGINE=sglang ARCH=cuda` at the `engine_runner.py install`
step. Every `pip install` of an sglang cuda step MUST instead run through the
`uv` binary the base provides (`/opt/llgenie/bin/uv`, on `PATH`) using
`uv pip install --system --break-system-packages`, matching the CUDA install
recipe of the sibling engines (vllm, tensorrt-llm, litert, freetoken) and
sglang's own torch preinstall step.

#### Scenario: the cuda install steps run through uv, never through pip

Given the `sglang` skill and shared generator,
When  `make generate-engine-params ENGINE=sglang` renders the cuda variant,
Then  `install.cuda` contains two `uv pip install --system --break-system-packages`
steps — the `python[all]` editable install and the AOT-kernels editable install —
and NO `python3 -m pip` string appears in the cuda install recipe.

- **Test:** `tests/test_engine_skills.py::test_sglang_cuda_install_uses_uv_not_pip`
  and `tests/test_engine_params_live.py` (regenerated params match committed).

#### Scenario: the committed cuda params and Dockerfile carry the uv-only recipe

Given the change edits the skill,
When  `make generate-engine-params ENGINE=sglang` regenerates params and the
Dockerfile from the skill,
Then  the committed `containers/engines/params/sglang.json` `variants.cuda.install`
and `containers/engines/dockerfiles/sglang/Dockerfile.cuda` reflect the uv-only
recipe, and `make check-engine-params` is green.

- **Test:** `make check-engine-params`, `make check-engine-source`,
  `make check-engine-coverage`

### Requirement: the sglang/cuda cell builds and detects on the engine-build pipeline

When the engine-build workflow builds the sglang cuda cell at this change's head,
the build MUST succeed (no `No module named pip`) and the image's binary MUST
answer the flags/detect the skill documents.

#### Scenario: a built sglang/cuda cell installs and detects

Given the committed params and the engine-build CI dispatch,
When  the `engine-image-sglang-cuda` job runs `make build-engine ENGINE=sglang
ARCH=cuda` then `make test-engine-stage ENGINE=sglang ARCH=cuda TEST=detect`,
Then  both succeed — the install steps run through uv on the pip-less base and
the image answers its documented binary flags.

- **CI job** `engine-image-sglang-cuda` -> `make build-engine` + `make test-engine-stage TEST=detect`

### Requirement: no other engine's pip usage is touched

The rocm cell and unrelated engines' `pip`/`python3 -m pip` usage MUST be
unchanged — the pip-less base is cuda-specific, so only the cuda install steps
are rewired.

#### Scenario: rocm keeps its pip usage

Given the change edits only sglang's `install.cuda`,
When  `make generate-engine-params ENGINE=sglang` regenerates,
Then  `variants.rocm.install` keeps its `pip list`/`python3 -m pip` steps
(its base `rocm/pytorch:...` ships pip), and no other engine's params change.

- **Test:** `make check-engine-params` (no unrelated param diff), OpenSpec `Not covered` names #1240/#1241/#1196.
