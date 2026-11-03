import json, sys
sys.path.insert(0, 'scripts')
from pathlib import Path
import sync_registry as sr


_README = ("# up\n\n## ❤️ Most loved open-weight models\n\n"
           "| Model | Status | Trend | CUDA t/s (best) | Metal t/s (best) | CPU t/s (best) | "
           "ROCm t/s (best) | VRAM | Why people love it |\n"
           "|---|---|---|---|---|---|---|---|---|\n"
           "| [**Q1**](https://huggingface.co/x/q1) | t | 1 | "
           "**500** t/s<br>[MegaCapybara](https://github.com/org/me) | — | — | — | "
           "**16GB**<br><sub>stated</sub> | y |\n")

_MEASUREMENTS = {"q1": [{"engine": "MegaCapybara", "tps": "500", "date": "2026-10-05",
                         "source_post": "https://x/2"}]}


def test_check_consults_the_vendored_measurements_sibling(tmp_path):
    """`check()` on a fresh clone consults the committed measurements.json sibling:
    the README's CUDA-best engine that only the measurement store records is accepted.

    Before fa92a107 the measurements store was never committed, so on a fresh tree
    `check()` silently fell back to the row-only engine list and false-rejected an
    engine that only the measurement store records (the MegaCapybara class). This
    pins that the vendored sibling is read by the committed check() path."""
    # A store row that fully satisfies the VENDORED contract: take a real committed
    # model as the skeleton (it already passes check_contract), then trim its row's
    # inline engines so the README-best engine lives only in the concerns store.
    real = json.loads(sr.VENDORED.read_bytes())
    model = next(m for m in real["models"] if m["id"] == "qwen3.8-27b")
    import copy
    model = copy.deepcopy(model)
    model["id"] = "q1"
    model["name"] = "Q1"
    model["full_name"] = "Q1"
    # Strip the row's inline engines AND supported_engines so the README's CUDA-best
    # (MegaCapybara) exists ONLY in the measurements sibling — the fresh-clone
    # consult is load-bearing (a real row's supported_engines would accept it).
    model["engines"] = [{"engine": "llama.cpp", "tps": "10", "date": "2026-10-01",
                         "source_post": "https://x/1"}]
    model["supported_engines"] = ["llama.cpp"]
    # Keep the real committed llama.cpp engine entry (contract-valid).
    store = {"engines": {"llama.cpp": real["engines"]["llama.cpp"]},
             "models": [model]}

    # Fresh-clone layout: model_contract + models + measurements + README siblings.
    (tmp_path / sr.VENDORED_CONTRACT.name).write_bytes(sr.VENDORED_CONTRACT.read_bytes())
    (tmp_path / sr.VENDORED_README.name).write_text(_README)
    (tmp_path / sr.VENDORED_MEASUREMENTS.name).write_text(
        json.dumps(_MEASUREMENTS, indent=2) + "\n")
    # Hermetic link snapshot so check() probes recorded answers, not the live Hub.
    answers = tmp_path / "readme-link-answers.json"
    answers.write_text(json.dumps(
        {"links": {"https://huggingface.co/x/q1": "200",
                   "https://github.com/org/me": "200"}}) + "\n")
    dest = tmp_path / sr.VENDORED.name
    dest.write_text(json.dumps(store, indent=2) + "\n")

    # The committed measurements sibling makes check() accept the measurements-only engine.
    assert sr.check(dest, snapshot=answers) == 0

    # Without it (the pre-fix fresh-clone state), the same engine false-rejects.
    (tmp_path / sr.VENDORED_MEASUREMENTS.name).unlink()
    assert sr.check(dest, snapshot=answers) == 1
