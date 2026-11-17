## ADDED Requirements

### Requirement: The shipped ollama cells pin one version across skill and generated companions

The ollama engine skill SHALL pin exactly one upstream version, and every generated companion —
the per-arch Dockerfile install/COPY paths, `containers/engines/params/ollama.json`, and the
`containers/engines/binaries.json` manifest — SHALL carry binary paths for that same version, so a
build cell cannot stage the new binary while its binary stage probes the old path.

#### Scenario: Skill pin moves to v0.40.16

- **WHEN** `skills/engines/ollama/SKILL.md` pins `ref: v0.40.16` with `pinned:` set to the
  upstream tag object sha
- **THEN** `make check-engine-params` passes against the regenerated dockerfiles, params, and
  binaries manifest, and every ollama binary path in `containers/engines/binaries.json` names
  `/opt/llgenie/engines/ollama/0.40.16/bin/ollama`

#### Scenario: Binary stage matches the staged tree

- **WHEN** a CI engine-build cell for ollama cpu or cuda finishes staging
- **THEN** the `test-engine-stage` probe finds the pinned binary at the manifest path and the cell
  is green (issue #2866 acceptance)

### Requirement: A pin re-derivation re-checks the install recipe against the upstream diff

Before moving the ollama pin, the lane SHALL compare the upstream tag range for changes that touch
the build (release Dockerfiles, `llama/server` presets, CMake wiring) and record in the skill text
what changed and why the recipe does or does not change.

#### Scenario: v0.40.15 → v0.40.16 diff reviewed

- **WHEN** the pin moves from `v0.40.15` to `v0.40.16`
- **THEN** the change set records that the only build-touching upstream diff is
  `llama/server/CMakePresets.json` widening `CMAKE_CUDA_ARCHITECTURES` to `103;121` for the
  windows-arm64 preset, leaving the Linux cpu/cuda/rocm install steps unchanged
