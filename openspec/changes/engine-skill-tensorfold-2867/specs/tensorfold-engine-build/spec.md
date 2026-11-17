## ADDED Requirements

### Requirement: The shipped tensorfold cells pin one version across skill and generated companions

The tensorfold engine skill SHALL pin exactly one upstream version, and every generated companion —
the per-arch Dockerfiles, `containers/engines/params/tensorfold.json`, and the
`containers/engines/binaries.json` manifest — SHALL carry binary paths for that same version, so a
build cell cannot stage the new binary while its binary stage probes the old path.

#### Scenario: Skill pin moves to v1.2.9

- **WHEN** `skills/engines/tensorfold/SKILL.md` pins `ref: v1.2.9` with `pinned:` set to the
  upstream tag object sha
- **THEN** `make check-engine-params` passes against the regenerated dockerfiles, params, and
  binaries manifest, and every tensorfold binary path in `containers/engines/binaries.json` names
  `/opt/llgenie/engines/tensorfold/1.2.9/bin/tensorfold`

#### Scenario: CUDA binary stage matches the staged tree

- **WHEN** the CI engine-build cell for tensorfold cuda finishes staging
- **THEN** the `test-engine-stage` probe finds the pinned binary at the manifest path and the cell
  is green (issue #2867 acceptance)

### Requirement: A pin re-derivation re-checks the zig build interfaces at the new tag

Before moving the tensorfold pin, the lane SHALL compare the pinned build interfaces the cuda
recipe depends on — the upstream `.zig-version`, the `release_sms` arch list in
`zig/build/cuda.zig`, and the installed artifact name — and record in the skill text what changed
and why the recipe does or does not change.

#### Scenario: v1.2.5 → v1.2.9 interfaces reviewed

- **WHEN** the pin moves from `v1.2.5` to `v1.2.9`
- **THEN** the change set records that `.zig-version` is unchanged (`0.17.0`), `release_sms` is
  unchanged (`80,86,120,121`), and the `tensorfold` install artifact name is unchanged, so the
  zig source-build recipe carries unchanged
