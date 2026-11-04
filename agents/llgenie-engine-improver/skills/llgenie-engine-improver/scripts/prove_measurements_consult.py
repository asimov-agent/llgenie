"""Prove that sync_registry.check() CONSULTS the vendored measurements.json sibling.

A single green check() run proves nothing: the store may satisfy the check without the
sibling (a row's inline `engines` or `supported_engines` accepts the README best engine).
The proof is the PAIR: exit 0 with the sibling, exit 1 without it.

Run from the repo root inside llgenie/test:latest (parent repo mounted for worktree git):
    python scripts/prove_measurements_consult.py

Expected output:
    with-meas CHECK_RET 0
    without-meas CHECK_RET 1

A `without-meas CHECK_RET 0` means the fixture is not load-bearing (see the fixture
trap in references/registry-contract-following.md) or the consult is decorative.
"""
import copy
import json
import pathlib
import sys

sys.path.insert(0, '.')
from scripts import sync_registry as sr  # noqa: E402

TMP = pathlib.Path('/tmp/consult-probe')
TMP.mkdir(exist_ok=True)

# The vendored contract sibling is required or check_contract fails for a missing schema
# rather than for the assertion we care about.
(TMP / sr.VENDORED_CONTRACT.name).write_bytes(sr.VENDORED_CONTRACT.read_bytes())

README = (
    "# up\n\n## \u2764\ufe0f Most loved open-weight models\n\n"
    "| Model | Status | Trend | CUDA t/s (best) | Metal t/s (best) | CPU t/s (best) | ROCm t/s (best) | VRAM | Why people love it |\n"
    "|---|---|---|---|---|---|---|---|---|\n"
    "| [**Q1**](https://huggingface.co/x/q1) | t | 1 | **500** t/s<br>[MegaCapybara](https://github.com/org/me) "
    "| \u2014 | \u2014 | \u2014 | **16GB**<br><sub>stated</sub> | y |\n"
)
(TMP / sr.VENDORED_README.name).write_text(README)

# The engine named by the README exists ONLY here.
MEAS = {"q1": [{"engine": "MegaCapybara", "tps": "500", "date": "2026-10-05",
                "source_post": "https://x/2"}]}
(TMP / sr.VENDORED_MEASUREMENTS.name).write_text(json.dumps(MEAS, indent=2) + "\n")

real = json.loads(sr.VENDORED.read_bytes())
model = copy.deepcopy(real['models'][0])
model['id'] = 'q1'
model['name'] = 'Q1'
model['full_name'] = 'Q1'
# Strip BOTH engine lists: either one would accept MegaCapybara and hide a decorative consult.
model['engines'] = [{"engine": "llama.cpp", "tps": "10", "date": "2026-10-01",
                     "source_post": "https://x/1"}]
model['supported_engines'] = ['llama.cpp']
store = {"engines": {"llama.cpp": real['engines']['llama.cpp']}, "models": [model]}
(TMP / sr.VENDORED.name).write_text(json.dumps(store, indent=2) + "\n")

# Record the invented URLs as live so check() skips the real link liveness probe.
answers = TMP / 'readme-link-answers.json'
answers.write_text(json.dumps({"links": {
    "https://huggingface.co/x/q1": "200",
    "https://github.com/org/me": "200",
}}) + "\n")

for variant in ("with-meas", "without-meas"):
    if variant == "without-meas":
        (TMP / sr.VENDORED_MEASUREMENTS.name).unlink()
    ret = sr.check(TMP / sr.VENDORED.name, snapshot=answers)
    print(f"{variant} CHECK_RET {ret}")
