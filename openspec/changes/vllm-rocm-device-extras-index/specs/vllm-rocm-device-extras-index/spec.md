# vllm-rocm-device-extras-index

## MODIFIED Requirements

### Requirement: The vllm rocm editable install resolves TheRock device packages from the AMD index

The `vllm` skill's `install.rocm` final editable install (`VLLM_TARGET_DEVICE=rocm
uv pip install --system --break-system-packages --no-build-isolation -e .`) MUST pass the AMD
multi-arch wheel index (`https://repo.amd.com/rocm/whl-multi-arch/`) as an additional index and
`--index-strategy unsafe-best-match`, matching how the preceding `-r requirements/build/rocm.txt`
step already resolves the same index. The regenerated `containers/engines/params/vllm.json` rocm
variant's install MUST then carry those index args in its step 4, so uv resolves `rocm[device-gfx*]`
(and any sibling TheRock device package) to the real AMD sdist/wheel and never to the default-PyPI
`rocm==0.1.0` placeholder.

#### Scenario: step 4 resolves rocm'S device extras from the AMD index

Given the pinned vllm source where `setup.py::get_rocm_device_requirements()` emits
`rocm[device-gfx<arch>]` while `rocm_sdk` is importable,
When  `make generate-engine-params ENGINE=vllm` renders the rocm variant,
Then  `install[3]` contains `--extra-index-url https://repo.amd.com/rocm/whl-multi-arch/` and
`--index-strategy unsafe-best-match`, and a local `uv pip install --dry-run rocm[device-gfx1100]`
with those args resolves `rocm==7.14.x` plus `rocm-sdk-core`, `rocm-sdk-device-gfx1100` and
`rocm-sdk-libraries` and does NOT select `rocm==0.1.0`.

- **Test:** `tests/test_engine_skills.py` (regenerate reproducibility) +
  `tests/test_engine_source_guard.py` (command parse), plus the optional local `uv --dry-run`.

#### Scenario: the rocm cell builds and publishes green

Given the committed change on the branch,
When  the engine-build workflow is dispatched for `engine=vllm arch=rocm`,
Then  the `push=false` build+verify run is green and the `push=true` run publishes the `:rocm`
image whose digest answers its probe.

- **Test:** CI engine-build vllm rocm run, `push=false` then `push=true`, both at the PR head sha.
