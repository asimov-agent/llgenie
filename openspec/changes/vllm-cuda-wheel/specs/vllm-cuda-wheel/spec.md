# vllm-cuda-wheel

## MODIFIED Requirements

### Requirement: vLLM cuda cell installs the pinned prebuilt CUDA wheel, not a source compile

The `vllm` skill's `install.cuda` MUST install the pinned official prebuilt CUDA wheel
(`vllm-0.33.0-cp38-abi3-manylinux_2_28_x86_64.whl`, sha256
`4b6bdec4ab269990bf70d45a3c1e94c3760a27064513760193b26d6f0da883aa`) with a `curl` + `sha256sum -c`
hash check, preceded by the cu130 torch family from `--index-url
https://download.pytorch.org/whl/cu130`. The cuda install MUST NOT run `git clone`, `-e .`, `-r
…/build/cuda.txt` or `build_rust.sh`. The `container.cuda` block MUST carry `prebuilt: false`
with the wheel recorded as the install source, and the generated `Dockerfile.cuda` MUST keep `FROM
llgenie/base-cuda:79cfaf25ba`. The `install.rocm` and `install.cpu` flows are unchanged.

#### Scenario: the generated cuda install is a hash-pinned wheel flow

Given the regenerated `containers/engines/params/vllm.json` cuda variant,
When  the source-build guard and the params read it,
Then  it contains NO `git clone`, NO `-e .`, NO `requirements/build/cuda.txt`, NO `build_rust.sh`;
it DOES contain the wheel URL, `sha256sum -c`, and `uv pip install` of
`--index-url https://download.pytorch.org/whl/cu130` followed by the wheel.

- **Test:** `tests/test_engine_skills.py` (`test_vllm_cuda_installs_the_wheel_not_a_source_step`)
  and `scripts/engine_source_guard.py check` (vllm/cuda is a tracked KNOWN_NOT_SOURCE cell).

#### Scenario: rocm and cpu still source-compile the pin

Given the regenerated rocm and cpu variants,
When  the params are read,
Then  their install steps still contain the pinned `git clone` and the `-e .` build for that
backend, with `prebuilt: false`.

- **Test:** `tests/test_engine_skills.py` (rocm/cpu install still carries the source build).
