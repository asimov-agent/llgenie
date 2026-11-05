# vLLM build: helper libs must come from the SAME backend index as torch

**Symptom (grounded, issue #1365 run 41345449621 cpu):** the cpu image build compiles and
installs `vllm==0.32.0+cpu` fine, but `vllm --version` dies at import with
`RuntimeError: operator torchvision::nms does not exist` (traceback through
`transformers.image_utils` -> `torchvision` -> `_meta_registrations.py`
`register_fake("torchvision::nms")`).

**Root cause:** `requirements/build/cpu.txt` pins `torch==2.13.0+cpu` (a repack only the
PyTorch `cpu` index serves) but asks for *bare* `torchvision`/`torchaudio` (no `+cpu`
suffix). Under `--index-strategy unsafe-best-match` uv resolves those helper libs from
default PyPI, whose `_C` extension was compiled against the *non-`+cpu`* torch ABI. On
import the `torchvision::nms` native op never registers, so the fake-kernel registration
fails with "operator does not exist".

**Fix:** preinstall the ABI-matched wheels from the **same** index as torch:
```yaml
- "uv pip install --system --break-system-packages torch==2.13.0 torchvision torchaudio --index-url https://download.pytorch.org/whl/{torch_backend}"
```
and only then run `-r {src}/requirements/build/cpu.txt` (its bare torchvision/torchaudio
rows stay satisfied by the already-present `+cpu` builds). The `cpu` index does serve
`torchvision-0.28.0+cpu-…-manylinux_2_28_x86_64.whl` (the ABI pair for torch 2.13.0);
grep the PEP-503 page rather than assuming a bare `torchvision==` pin.

**General rule for every backend:** any torch-adjacent compiled lib (torchvision,
torchaudio, torchcodec, triton) must resolve from the *same* wheel index as torch — a
bare name pulling from another index yields silently-unregistered custom ops at import.

**Also seen:** rocm leg — bare `triton` pin contradicts its own `torch==…+rocm` -> sed the
vendored `requirements/build/<arch>.txt` to the suffixed wheel before the build-requirements
install (upstream pin defect). Verify with `scripts/engine_skills.py params --check` for the
engine; the JSON is generated, never hand-edited.
