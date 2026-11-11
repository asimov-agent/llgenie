# engine-bump-daily

## ADDED Requirements

### Requirement: The regen guard judges the delta regen itself created

`_regen_guard` MUST snapshot the `git status --porcelain` path set before running
`make generate-engine-params` and again after it, and apply the foreign-path rejection only
to paths new in the second read. Paths already dirty when the guard started are baseline —
written by sanctioned earlier steps of the same bump (this engine's apply/sync, an earlier
engine's completed bump in the same `bump_daily` loop) — and MUST NOT fail the guard. The
ownership allow-list and the error text (`regen changed a file outside <engine>: <path>`)
are unchanged.

#### Scenario: a prior engine's completed bump does not fail the next engine's guard

- **Given** the baseline `git status` already carries `containers/engines/dockerfiles/llama.cpp/Dockerfile.cpu`
  dirty from llama.cpp's completed bump in the same `bump_daily` run
- **And** `make generate-engine-params ENGINE=testengine` succeeds
- **And** the post-regen `git status` shows the prior dirt plus `containers/engines/params/testengine.json`
- **When** `_regen_guard("testengine")` runs
- **Then** it returns `["containers/engines/params/testengine.json"]` and does not raise
- **Test:** `tests/test_engine_bump.py::test_regen_guard_ignores_a_prior_engine_s_dirtiness`

#### Scenario: a regen that rewrites another engine's file from a clean baseline still fails

- **Given** the baseline `git status` is clean
- **And** `make generate-engine-params ENGINE=testengine` succeeds
- **And** the post-regen `git status` shows `containers/engines/params/other.json`
- **When** `_regen_guard("testengine")` runs
- **Then** it exits non-zero naming `outside testengine`
- **Test:** `tests/test_engine_bump.py::test_regen_guard_isolates_engine` (updated fake:
  first status read clean, second read foreign)
