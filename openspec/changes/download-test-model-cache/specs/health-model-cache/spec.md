## ADDED Requirements

### Requirement: The health-model download lands in the shared stage HOME and survives its run

`make download-test-model` SHALL run the downloader with `HOME` set to the same stage HOME the health stage reads (`$(CI_HOME)` = `<repo>/.ci-home`) — on Linux in a uid-mapped container with the checkout mounted at its own path, on macOS natively with `env HOME=$(CI_HOME)` — so the fetched model file persists on the host after the target returns. The target SHALL NOT run the downloader in a throwaway container HOME that discards the file.

#### Scenario: the model survives the download stage

- **WHEN** `make download-test-model` completes on a clean checkout
- **THEN** `<repo>/.ci-home/models/Qwen/8GB/qwen2.5-0.5b-instruct-q4_0.gguf` exists on the host

#### Scenario: a second download run is a no-op

- **WHEN** `make download-test-model` runs again with the model already present
- **THEN** the downloader prints its `already present` line and exits 0 without fetching

### Requirement: Stage clean keeps the model cache, wipes the rest

`CI_HOME_CLEAN` (both OS branches) SHALL remove the stage-scratch contents of `$(CI_HOME)` but SHALL NOT delete its `models` subtree, so a model fetched by any stage is reused by every later stage in the same workspace and the loop pays for the health download once.

#### Scenario: health stage's own download step short-circuits

- **WHEN** a bracketed stage runs `test-health-host`'s download step after an earlier stage provisioned the cache
- **THEN** the step reports the model `already present` instead of fetching again

#### Scenario: scratch is still cleaned

- **WHEN** `CI_HOME_CLEAN` runs on a `.ci-home` containing stage scratch and a `models` subtree
- **THEN** everything except `models` is removed

### Requirement: The seams are locked by tests

Tests SHALL pin the `MODEL_CACHE_RUN` macro in both OS branches (HOME = `$(CI_HOME)`; Linux uid-mapped with the checkout mounted at its own path), the `download-test-model` recipe shape (`mkdir -p $(CI_HOME)` then `$(MODEL_CACHE_RUN)`), and the models-preserving shape of both `CI_HOME_CLEAN` variants.

#### Scenario: seam drift reddens the unit battery

- **WHEN** the shared-HOME run, the mkdir, or the models-keeping clean is removed from the Makefile or `mk/tests.mk`
- **THEN** `tests/test_health_model_cache.py` fails
