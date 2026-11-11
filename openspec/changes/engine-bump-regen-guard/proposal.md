# Engine-bump: the regen guard must judge regen's own delta, not the cumulative tree

## Why

`_regen_guard` (scripts/engine_bump.py) runs `make generate-engine-params` and then fails if
ANY path in `git status --porcelain` is foreign to the bumped engine. `bump_daily` loops
`bump()` over every moved engine without committing between engines, so from the second
engine onward the porcelain carries the earlier engines' completed bumps. Measured 2026-11-11
at `origin/main` `b2e3b1ec4`: 4 engines moved, llama.cpp bumped fully, then ollama, strata and
tensorfold each failed with `regen changed a file outside <engine>:
containers/engines/dockerfiles/llama.cpp/Dockerfile.cpu` — dirt llama.cpp's own bump wrote.
The weekly `engine-bump.yml` job can therefore never open a bump PR whenever ≥2 engines move
in a week: 4 engines have aged unpublished since 2026-11-02 (10 of 28 image cells 404).
Issue: #2506.

## What Changes

- `_regen_guard` snapshots the porcelain path set BEFORE `generate-engine-params` and again
  after it, and guards only the NEW delta (`after − before`): dirt that already existed when
  the guard started is baseline — written by sanctioned earlier steps (this engine's apply, an
  earlier engine's completed bump) — not a regen side effect.
- A genuine cross-engine side effect — regen rewriting another engine's params/Dockerfile/SKILL
  from a baseline that did not carry it — still fails exactly as today.
- The four existing guard tests' fake `git status` responses become call-sequence-aware
  (first read = baseline, second read = post-regen), preserving each test's original verdict.
- One new test covers the multi-engine shape: a prior engine's dirtiness must not fail the
  next engine's guard.

## Impact

- `scripts/engine_bump.py` — `_regen_guard` gains a `_porcelain_paths()` helper and a
  before/after diff; the per-path ownership check and error text are unchanged.
- `tests/test_engine_bump.py` — §"Regen guard + changed-engines scoping": 5 existing fakes
  updated, 1 new test added.
- Affected specs: `engine-bump-daily`.
- No Makefile, CI workflow, or data change; `bump-daily`'s CLI surface is unchanged.
