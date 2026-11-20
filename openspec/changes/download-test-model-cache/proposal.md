# Download the health model into the shared stage HOME

## Why

`make download-test-model` fetches the 0.43 GB health model into the test container's throwaway HOME (`--rm`), so the bytes never survive the command; `make test-health` then re-fetches the same file into `$(CI_HOME)` (`<repo>/.ci-home`, the HOME its `test-health-host` step actually reads) and `$(CI_HOME_CLEAN)` wipes that tree at the end of every bracketed stage. `make loop` therefore pays the download twice per run, CI's health job pays it again, and the target's advertised cache path does not exist after it returns. Issue #356.

## What Changes

- A per-branch `MODEL_CACHE_RUN` macro runs the downloader with `HOME=$(CI_HOME)` and the checkout mounted at its own path (Linux: uid-mapped container with `-v "$(ROOT)":"$(ROOT)"`; macOS: native venv run with `env HOME=$(CI_HOME)`), so the model lands at `<repo>/.ci-home/models/Qwen/8GB` and survives the container.
- `download-test-model` creates `$(CI_HOME)` first and runs through `MODEL_CACHE_RUN`; its docstring now names the real destination.
- `CI_HOME_CLEAN` (both OS branches) stops deleting the `models` subtree: stage scratch is still wiped, the model cache is kept, so every later stage's own download step short-circuits via the downloader's present-file check.
- New makefile-seam tests pin: the recipe runs through `MODEL_CACHE_RUN` after `mkdir -p $(CI_HOME)`; both branches' `MODEL_CACHE_RUN` set HOME to `$(CI_HOME)`; both branches' `CI_HOME_CLEAN` preserve `models` while remaining the same macro used by every stage bracket.

## Impact

- Affected specs: `health-model-cache` (new capability)
- Affected code: `Makefile`, `mk/tests.mk`, `tests/test_makefile_tests_mk_split.py`-adjacent seam pins (new test file `tests/test_health_model_cache.py`), agent-wiki + changes.d docs
- Not affected: engine stage brackets (`ENGINE_TEST_ARGS`, `CI_HOME_CLEAN` macro name and call sites), `scripts/download_test_model.py` logic (idempotence already exists), the downloader's HF resume/throttle path
- Not covered: host-side serving proof of `make test-health` ("hi") — gated on human permission to start inference engines; CI's `cpu-health` job covers it
