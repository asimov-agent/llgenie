import json, sys
sys.path.insert(0, 'scripts')
import sync_registry as sr
from pathlib import Path

# A README whose CUDA-best engine exists ONLY in the measurements store (not the model row).
# The producer's #689 normalized store moved per-model t/s detail into data/measurements.json.
# check_readme_matches must accept an engine the measurement store records (issue #1634).
def test_readme_engine_from_the_measurement_store_is_accepted():
    store = {
        "engines": {"llama.cpp": {}},
        "models": [{"id": "q1", "name": "Q1", "vram_tier": "16GB",
                     "supported_engines": ["llama.cpp"],
                     "engines": [{"engine": "llama.cpp", "tps": "10", "date": "2026-10-01",
                                  "source_post": "https://x/1"}]}],
    }
    measurements = {"q1": [{"engine": "MegaFast", "tps": "500", "date": "2026-10-05",
                            "source_post": "https://x/2"}]}
    readme = ("# up\n\n## ❤️ Most loved open-weight models\n\n"
              "| Model | Status | Trend | CUDA t/s (best) | Metal t/s (best) | CPU t/s (best) | "
              "ROCm t/s (best) | VRAM | Why people love it |\n"
              "|---|---|---|---|---|---|---|---|---|\n"
              "| [**Q1**](https://huggingface.co/x/q1) | t | 1 | "
              "**500** t/s<br>[MegaFast](https://github.com/org/me) | — | — | — | "
              "**16GB**<br><sub>stated</sub> | y |\n")
    # Without the measurement store this is a false rejection:
    try:
        sr.check_readme_matches(store, readme)
        raise SystemExit("expected a false rejection without measurements")
    except ValueError as e:
        assert "MegaFast" in str(e)
    # With it, accepted:
    sr.check_readme_matches(store, readme, measurements)
