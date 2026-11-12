# tag-identity-repin-gate — Spec Delta

## ADDED Requirements

### Requirement: Repin detection compares tag identity, not only params-file text

`repinned_engine_ids` SHALL name every engine whose published tag identity changes between `base` and
the tree — including engines whose params file is byte-identical to the base while a Dockerfile,
entrypoint, or runner file those tags hash has changed — and SHALL still name every engine the
params-file diff names today. The comparison SHALL be computed from the tag digests
(`engine_image._current_tag` for the tree, `engine_image._tag_at` for `base`), never from a guess
about which files "usually" matter. Disabled variants SHALL not create a diff. An engine with no
params copy at `base` counts (first import).

#### Scenario: A Dockerfile-only change is detected as a repin
- **Given** a fixture repo whose engine `demo` has a params file byte-identical to `base` but whose
  `Dockerfile.cpu` bytes differ from `base`
- **When** `repinned_engine_ids(base)` runs
- **Then** `demo` is named, because the cpu cell's computed tag differs between the tree and `base`

#### Scenario: The params-file diff keeps naming what it names today
- **Given** a fixture repo whose engine `demo` has a params file whose text differs from `base`
- **When** `repinned_engine_ids(base)` runs
- **Then** `demo` is named even when the tag digests happen to be unchanged

#### Scenario: A clean branch repins nothing and probes nothing
- **Given** a branch whose engine files are identical to its base
- **When** `repinned_engine_ids(base)` runs, and `make check-engine-pins-published` runs with it
- **Then** the id list is empty and no registry probe is made (hermetic gate, unchanged)

#### Scenario: A first import counts
- **Given** a fixture repo whose engine `demo` params file has no copy at `base`
- **When** `repinned_engine_ids(base)` runs
- **Then** `demo` is named (nothing at `base` could have published it)

### Requirement: A retagging PR dispatches and waits for its own images

The pre-merge publisher `scripts/engine_build_trigger.py` SHALL dispatch scoped
`engine-build push=true` runs for every engine named by the union diff, so the PR that retags an
image is the PR that publishes it; the may-arm merge gate SHALL refuse to merge until each retagged
cell's exact tag resolves in the registry.

#### Scenario: The will-arm dispatches for a retagged engine
- **Given** a fixture diff whose only change is `containers/engines/dockerfiles/demo/Dockerfile.cpu`
- **When** `engine_build_trigger.py` computes its dispatch set for that diff
- **Then** a scoped dispatch `engine=demo` with `push=true` is in the set, and engines whose tags
  did not move are not in it

#### Scenario: The merged gate holds the retag until published
- **Given** a PR whose retagged engine's exact tag does not resolve in GHCR
- **When** the repin gate (`check_engine_pins_published` repin mode) checks that PR's head against
  its base
- **Then** the gate exits 1 naming the engine and the exact missing tag

### Requirement: The unit suite defers retagged engines on a moving base

`tests/test_ci_publish_order.py::_deferred_engines` SHALL defer exactly the engines named by the
shared tag-identity union diff when `base != head`, replacing the `scripts/engine_image.py`-text
special case of issue #823 with the general rule, and SHALL defer nothing when the tree equals its
base (so a main run still verifies every published tag against the registry).

#### Scenario: Retagged engines are deferred on a PR diff
- **Given** a change whose only edit is a variant Dockerfile
- **When** `_deferred_engines(base=merge-base)` computes the deferred set for the publish-order test
- **Then** the retagged engine is deferred (its tag is awaited by `make ci-wait-engine-images`, not
  demanded from the registry mid-PR)

#### Scenario: A main run defers nothing
- **Given** the tree at `HEAD` with `base == HEAD` (a main CI run)
- **When** `_deferred_engines(base=HEAD)` runs
- **Then** the deferred set is empty and every committed cell is checked against the registry
