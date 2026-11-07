# Surogate engine capability

## ADDED Requirements

### Requirement: Surogate is a shipped, servable cuda engine

The `surogate` engine becomes a shipped engine with a real, resolvable skill entry: the
regenerated registry, params and Dockerfile let `make check-engine-skill-gap` and
`make check-engine-params` pass, and the `engine-image-*` matrix builds the `cuda` cell.

#### Scenario: the gap gate resolves Surogate as shipped

- **Given** Surogate is a registry engine carried additively into `data/models.json` /
  `data/measurements.json` (nothing removed) and `skills/engines/surogate/SKILL.md` exists,
  pinned to a real upstream ref with backends `[cuda]`
- **When** `make check-engine-skill-gap` and `make skills-validate REGISTRY=data/models.json
  UNSUPPORTED=data/unsupported-engines.json` run
- **Then** Surogate is not an unresolved engine: the gap gate reports 0 unresolved and the
  registry-keys gate stays additive-green (nothing lost)

#### Scenario: the params and Dockerfile are committed and validated

- **Given** `make generate-engine-params ENGINE=surogate` has written
  `containers/engines/params/surogate.json` and `containers/engines/dockerfiles/surogate/Dockerfile.cuda`
- **When** `make check-engine-params` and `make check-engine-coverage` run
- **Then** the committed cell matches the skill and the engine is `built` for CI (its `cuda`
  variant is in the build matrix)

### Requirement: the wheel install is a recorded, deliberate source exception

The Surogate cell is `prebuilt=false` but runs no source build (it installs upstream's published
manylinux cu130 wheel — the wheel IS the engine), so `make check-engine-source` must pass with
the exception in `engine_source_guard.py::KNOWN_NOT_SOURCE`.

#### Scenario: the source guard accepts the wheel-only cell

- **Given** `(surogate, cuda)` is recorded in
  `scripts/engine_source_guard.py::KNOWN_NOT_SOURCE` with the wheel-install decision
- **When** `make check-engine-source` runs on the `surogate/cuda` cell
- **Then** the cell passes as a tracked exception and the gate is green
