# vllm/rocm: resolve `rocm[device-gfx*]` from the AMD index so the `-e .` install does not fall back to the PyPI `rocm==0.1.0` placeholder (#1558)

## Why

The vllm rocm engine-build leg fails at the editable install with:

```
Failed to build `rocm==0.1.0`
  Call to `poetry.core.masonry.api.build_wheel` failed (exit status: 1)
  [stderr] ModuleNotFoundError: No module named 'poetry'
  help: `rocm` (v0.1.0) was included because `vllm` ... depends on `rocm`
```

`rocm==0.1.0` is an AMD-OSS **placeholder** on the default PyPI index — a 606-byte
poetry-built sdist (`requires_python>=3.12`, no wheel, no `device-*` extras). The pinned
vllm source (`v0.33.0` = `4ba787ec`) emits the **real** TheRock dependency as per-target
extras — `rocm[device-gfx<arch>]`, `torch[device-gfx<arch>]`, `torchvision[device-gfx<arch>]` —
from `setup.py::get_rocm_device_requirements()`, but only while the `rocm_sdk` module is
importable. Step 2 (`-r requirements/build/rocm.txt`) installs `rocm==7.14.0` (a setuptools
meta-package that provides `rocm_sdk`) from the AMD index, so at step 4 `rocm_sdk` IS
importable and the extras MUST resolve from that same index (`repo.amd.com/rocm/whl-multi-arch/`).
Step 4's `uv pip install --no-build-isolation -e .` does **not** carry the AMD index, so uv
falls back to the default-PyPI `rocm==0.1.0` placeholder and the poetry build dies under
`--no-build-isolation`.

The rocm cell cannot be built or published while this stands.

## What changes

1. `skills/engines/vllm/SKILL.md` `install.rocm` step 4: add the AMD wheel index and
   `unsafe-best-match` resolution to the `-e .` editable install, exactly as step 2 resolves
   `requirements/build/rocm.txt` against the same index — so `rocm[device-gfx*]` and the other
   TheRock device packages resolve to the real AMD sdist/wheel, never the PyPI placeholder.
2. `make generate-engine-params ENGINE=vllm` regenerates `containers/engines/params/vllm.json`
   (rocm `install[3]` gains the index args); `Dockerfile.rocm` unchanged (install commands live
   in params).
3. A local uv resolve/dry-run of the affected install set proves `rocm==0.1.0` is no longer
   selected (it resolves to `rocm==7.14.x` + `rocm-sdk-device-gfx*`).
4. Drive the engine-build vllm arch=rocm cell green (`push=false` build+verify, then `push=true`
   publish), recording both run ids at the head sha.

## Impact

- `skills/engines/vllm/SKILL.md` (comment + step 4 of `install.rocm`).
- `containers/engines/params/vllm.json` (regenerated).
- `docs/ENGINES.md`, `agent-wiki/2026-11-02-vllm-rocm-device-extras-index.md`,
  `CHANGES.md` + `docs/changes.d/`.
- Tests: `tests/test_engine_source_guard.py` (parse-only; command shape unchanged apart from
  the index args), `tests/test_engine_skills.py` (regenerate reproducibility).

## Not covered

- vllm/cuda and vllm/cpu rows — unaffected (their installs never emit `rocm[device-*]`).
- The unit-test pin (#1553).

## Proof

`uv pip install --dry-run rocm[device-gfx1100] --extra-index-url
https://repo.amd.com/rocm/whl-multi-arch/ --index-strategy unsafe-best-match` resolves
`+ rocm==7.14.1`, `+ rocm-sdk-core==7.14.1`, `+ rocm-sdk-device-gfx1100==7.14.1`,
`+ rocm-sdk-libraries==7.14.1` (no `rocm==0.1.0`); the same command without the AMD index
resolves `+ rocm==0.1.0` with `warning: does not have an extra named device-gfx1100` — the
exact failing class.
