# vllm rocm torch-pin: check the AMD index, not download.pytorch.org

A "torch==X+rocmY unsatisfiable" claim on the vllm rocm row is only true if the
AMD index is also empty. rocm.txt declares `--extra-index-url
https://repo.amd.com/rocm/whl-multi-arch/` and it SERVES the rocm wheels
(torch, torchvision, torchaudio, rocm-suffixed triton) that download.pytorch.org
never will.

Re-measure with the EXACT flag the install leg passes:

```bash
uv pip compile <rocm.txt> --python-version 3.12 \
  --python-platform x86_64-unknown-linux-gnu --index-strategy unsafe-best-match -o lock.txt
```

EXIT 0 against the real indexes proves satisfiability regardless of the issue's
prose (issue #1262 premise was disproven this way at main@514d45ba, pin
3a4d82f5; run 41402868957 downloaded torch==2.12.0+rocm7.14.0, 194MiB, inside
the docker build).

## A green resolve is NOT a green cell

The rocm cell can still fail after torch resolution at `uv pip install --no-build-isolation -e .`
on a NON-torch blocker. The vllm rocm-variant run-time dep `rocm==0.1.0` — a PyPI sdist-only
poetry-built package (https://pypi.org/pypi/rocm/0.1.0/json, requires-python >=3.12) — fails to
build under `--no-build-isolation` with `ModuleNotFoundError: No module named 'poetry'` because
`--no-build-isolation` tells uv "the backend is already here" and poetry is NOT in the rocm base.

The FIX is not to install poetry — it is to stop uv falling back to the PyPI placeholder at all.
Put the SAME AMD wheel index on the `-e .` compile line that `rocm.txt` already declares, so `rocm`
resolves to the prebuilt wheel instead of the sdist:

```
uv pip install --system --break-system-packages --no-build-isolation \
  --extra-index-url https://repo.amd.com/rocm/whl-multi-arch/ \
  --index-strategy unsafe-best-match -e .
```

Measured on the rocm base: with the AMD index `rocm` resolves to **`rocm==7.14.1` (+ `rocm-sdk-core`)
as prebuilt wheels in ~1.3s** — no source build, no poetry; without it uv picks the `rocm==0.1.0`
sdist and dies the same way for every rebuild. Confirm the split cheaply before a 4h build, in a
throwaway container from the base image (`scripts/probe_rocm_resolution.sh`):

```
uv pip install --dry-run --system --break-system-packages rocm --index-strategy unsafe-best-match
#   ->  + rocm==0.1.0          (PyPI placeholder; the -e . line will need poetry)
uv pip install --dry-run --system --break-system-packages rocm \
  --extra-index-url https://repo.amd.com/rocm/whl-multi-arch/ --index-strategy unsafe-best-match
#   ->  + rocm==7.14.1 +rocm-sdk-core   (prebuilt wheel; -e . resolves clean)
```

## AMD index facts

- repo.amd.com/rocm/whl-multi-arch/ returns 200 and a PEP 503 page per package.
- Packages the index does not host return **403** (not 404) — use
  `--index-strategy unsafe-best-match` or uv reads the 403 as fatal for the
  plain `first-match` strategy.
- amdsmi, tilelang are NOT on the AMD index (they come from PyPI) — that is fine
  under unsafe-best-match.
