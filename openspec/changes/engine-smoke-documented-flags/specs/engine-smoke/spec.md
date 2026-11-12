# engine-smoke-documented-flags

## ADDED Requirements

### Requirement: the engine binary smoke probes the flags the engine's own manifest documents

`scripts/engine_smoke.py` `binary_smoke` MUST probe, for a built image, the documented flag set
carried by the committed generated manifest (`containers/engines/binaries.json`, read through
`engine_image.variant_flags(spec)`), and for an installed host binary the set documented by the
skill (`engine_skills.documented_flags(skill, backend)`). The hardcoded `["-h", "--version"]` pair is
replaced by these documented sets. The `## Acceptance criteria` wording of issue #1717 ("the binary
answering the flags it documents") is the operative contract; issue #2319's ceiling survives as a
vocabulary bound: a documented flag outside `{-h, --help, --version}` MUST fail the smoke closed,
naming the engine and variant, exit non-zero. When the manifest (or skill) documents no flags, the
probe set MUST default to the pinned `["-h", "--version"]` (issue #2319's default preserved). A
variant whose manifest says `probe: device` MUST be skipped by the binary smoke exactly as before.

#### Scenario: mlx-cpu is smoked with its documented flag only

- Given the committed manifest entry `mlx/cpu → flags ["--help"], probe "help"`
- When the binary smoke runs for the built `mlx` cpu image
- Then the probe set is exactly `["--help"]`, no `--version` probe is attempted, and a binary that
  answers `--help` exits the smoke 0

#### Scenario: a both-flags engine still probes both

- Given the committed manifest entry `llama.cpp/cpu → flags ["--version", "--help"], probe "flags"`
- When the binary smoke runs for the built `llama.cpp` cpu image
- Then the probe set is exactly `["--version", "--help"]` and each flag's verdict is reported
  independently

#### Scenario: an engine documenting nothing keeps the pinned default

- Given a manifest entry with no `flags` key (or an empty list)
- When the binary smoke runs for that image
- Then the probe set is exactly `["-h", "--version"]`

#### Scenario: an out-of-vocabulary documented flag fails closed

- Given a manifest entry documenting a flag outside `{-h, --help, --version}` (e.g. `--dump-config`)
- When the binary smoke runs for that image
- Then the smoke exits non-zero naming the engine and variant, and no probe is run

#### Scenario: a device-probe variant is skipped, unchanged

- Given the committed manifest entry `vllm/cuda → probe "device"`
- When the binary smoke runs for the built `vllm` cuda image on a GPU-less runner
- Then the smoke prints the device-skip verdict and exits 0 without probing any flag

#### Scenario: the host skill path honors the per-backend map

- Given a skill whose `binary_flags` is a per-backend map (e.g. vllm's `cuda: ["--version"]`)
- When `binary_smoke` smokes the installed binary for the backend `cuda`
- Then the probe set is the map entry for that backend, not the union across backends
