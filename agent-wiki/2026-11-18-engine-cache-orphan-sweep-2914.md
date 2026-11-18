# GC of superseded fixed-name buildx cache tags (issue #2914)

## What and why

Before the cache-keying changes (#2891 / #2911) every engine build wrote its buildx registry
layer-cache to a FIXED name (`llgenie/<image>:buildcache`, `llgenie/<engine>:buildcache-<variant>`,
`llgenie/<name>:buildcache`) with no link to the content being built. The keying changes make every
build write a content-hash-keyed namespace instead; the old fixed tags stay in GHCR as orphaned
layers, consuming storage and quota.

Both keying PRs (#2912 engine, #2915 helper) are still OPEN, so at the head this work was written
against the fixed names are LIVE producers — a registry deletion now would destroy the cache current
builds still read and write. The issue's own gate forbids the sweep until both land.

## What this change ships

- `scripts/cache_orphan_report.py`: list (`report`/`list`) and `sweep` of the superseded fixed-name
  cache tags. Safety is derived from the ONE seams the builds call —
  `engine_image.cache_ref` and `ci_images.cache_ref` — so a fixed tag is an orphan only when it
  exists in the registry AND no producer seam still writes it. That makes the tool correct at every
  head with no second derivation: while the keying has not landed it prints zero orphans; the moment
  the keying lands the same seams return content-keyed names and the superseded tags surface as
  orphans automatically.
- `engine_image.cache_ref(image_name, variant)` — the single seam `build_base`/`build` now call
  (behavior-identical today; the keying PRs edit this one function).
- Make targets `engine-cache-orphan-report` / `engine-cache-orphan-sweep` (`mk/engines.mk` + `.PHONY`).
- Hermetic tests `tests/test_cache_orphan_report.py` (registry seam stubbed, producer seams real):
  75 passed across it + `tests/test_engine_force_rebuild.py` + `tests/test_ci_images.py`.
- `docs/ENGINES.md` GC section + this note + `docs/changes.d` fragment + regenerated `CHANGES.md`.

## Status / what is verified vs not

- Verified: the seam refactor is byte-identical (existing engine/ci cache-ref tests green, 71);
  orphan logic hermetic (75 host tests green); report/sweep wiring added and `.PHONY`.
- NOT run: the live registry sweep — both keying PRs are open, so it would delete live cache.
  AC2 (the tags gone, `make engine-cache-orphan-report` prints zero) is a post-landing verification
  the tool enables, not something this change can prove at this head.
- Not run in this container: the dockerized gates (`make test-unit`, `make openspec-validate`) and
  the dockerized OpenSpec CLI — this agent container has no docker, nerdctl, or node. The OpenSpec
  change is written in the CLI's exact on-disk format and the new tests are exercised directly with
  host pytest (75/green).

Implements #2914.
