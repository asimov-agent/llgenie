# registry-cache-hygiene

## ADDED Requirements

### Requirement: the repo names every superseded fixed-name cache ref it could have pushed

`scripts/registry_cache_orphans.py` MUST derive its orphan candidate set from the live repo
constants — `ci_images.IMAGES` (helpers), `engine_skills.BACKENDS` (bases), and
`engine_image.matrix()` (engine cells × variants) — and MUST NOT hardcode package or engine names.
Each candidate MUST be exactly one of the fixed-name cache shapes the two retired schemes wrote:
`llgenie/<helper-or-base>:buildcache` or `llgenie/<engine>:buildcache-<variant>`.

#### Scenario: a new engine or helper is covered without editing the sweep

- **Given** a new engine entry in `params/` or a new helper in `ci_images.IMAGES`
- **When** `make registry-cache-orphans` runs
- **Then** its `:buildcache` / `:buildcache-<variant>` ref is among the checked candidates
- **Test:** `tests/test_registry_cache_orphans.py` asserts every `ci_images.IMAGES` name, every
  `engine_skills.BACKENDS` backend, and every `engine_image.matrix()` (engine, variant) pair has its
  fixed-name candidate in `candidate_refs()`

#### Scenario: every candidate is a fixed-name cache tag

- **Given** the derived candidate set
- **When** each candidate's tag is matched against the orphan shape
- **Then** all match `^buildcache(-[a-z0-9]+)?$`
- **Test:** `tests/test_registry_cache_orphans.py`

### Requirement: deletion cannot touch a live ref

`gc` MUST refuse (non-zero, naming the ref) any ref whose tag is not the fixed-name cache shape:
content-keyed cache tags (`<pin>-<digest>-<variant>-buildcache`, `<12hash>-buildcache`) and ordinary
image tags (`latest`, `main`) MUST never pass the guard, and the version-delete call MUST only run
after the guard passes. `gc` without `--yes` MUST print what it would delete and exit non-zero
without deleting anything.

#### Scenario: a content-keyed cache tag is refused

- **Given** `ghcr.io/asimov-agent/llgenie/test:abc123def456-buildcache` and
  `ghcr.io/asimov-agent/llgenie/vllm:1.2.3-abcdef01-cuda-buildcache`
- **When** the guard is asked to accept them for deletion
- **Then** each raises naming the ref, and no delete call runs
- **Test:** `tests/test_registry_cache_orphans.py` exercises the guard directly with injected
  checker/deleter seams — hermetic, no network

#### Scenario: gc stays dry without the explicit flag

- **Given** injected probes that report two orphaned fixed refs
- **When** `run_gc(assume_yes=False)` runs
- **Then** it exits 1, names both refs, and the injected deleter recorded zero calls

### Requirement: the sweep is a make target, and CI never performs deletions

`make registry-cache-orphans` (report) and `make registry-cache-gc` (delete) MUST exist in
`mk/engines.mk`, and `make check-wiring` MUST see `scripts/registry_cache_orphans.py` wired to a
target and tested by `tests/test_registry_cache_orphans.py`. No workflow may invoke
`registry-cache-gc`: the registry deletions remain a human-side action after merge (the #746
registry-admin boundary), and the main pipeline stays tests-only.

#### Scenario: wiring gate green

- **Given** the new script, target pair, and test module
- **When** `make check-wiring` and `make check-proc-gate` run
- **Then** both exit 0 (the script uses only the `scripts/proc.py` seam for subprocesses)
- **Test:** the two gates themselves at the PR head
