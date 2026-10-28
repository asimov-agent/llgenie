# engine-skill-scaffold

## ADDED Requirements

### Requirement: the scaffold derives `os:` from the backend evidence it already reads

`make engine-skill-scaffold ENGINE="<registry name>"` MUST write an `os:` list derived from the
backends it derived for the skill (the registry's `backend` string, or `BACKENDS=` when the caller
supplies it): `metal` alone MUST be `os: [darwin]`, `metal` plus any of `cuda`/`rocm`/`vulkan`/`cpu`
MUST be `os: [darwin, linux]`, and a backend list with no `metal` MUST be `os: [linux]`. It MUST NOT
claim `linux` for an engine whose only backend is Metal, and the scaffolded body MUST state which
evidence produced the value.

WHEN a registry engine's only backend is Metal
THEN the scaffold writes `os: [darwin]`, so no Linux image is demanded for it.

#### Scenario: a Metal-only registry entry is scaffolded as darwin

- **Given** a registry entry whose `backend` is `Metal` and whose repo is an Apple-Silicon server
- **When** `make engine-skill-scaffold ENGINE=<that engine>` runs
- **Then** `skills/engines/<id>/SKILL.md` carries `backends: [metal]` and `os: [darwin]`
- **And** `engine_skills.container_spec()` renders no image for it, so `validate()` raises no
  "no container image for" error
- **Test:** `tests/test_engine_skill_scaffold.py::test_a_metal_only_registry_entry_scaffolds_darwin_only`

#### Scenario: a Linux backend still scaffolds linux

- **Given** a registry entry whose `backend` is `CUDA / ROCm / CPU`
- **When** `make engine-skill-scaffold ENGINE=<that engine>` runs
- **Then** the skill carries `os: [linux]`
- **And** `container_spec()` renders an image for its container backends
- **Test:** `tests/test_engine_skill_scaffold.py::test_a_linux_backend_registry_entry_scaffolds_linux`

#### Scenario: both oses only when the registry names both

- **Given** one registry entry whose `backend` is `CUDA / Metal` and one whose only backend is `Metal`
- **When** the scaffold runs for each
- **Then** the dual-backend skill carries `os: [darwin, linux]`
- **And** the Metal-only skill carries `os: [darwin]` and never `linux`
- **Test:** `tests/test_engine_skill_scaffold.py::test_a_dual_backend_engine_scaffolds_both_oses_only_when_the_registry_names_both`

#### Scenario: an explicit --backends list is the evidence too

- **Given** a registry entry whose wording names no backend, scaffolded with `BACKENDS=rocm,vulkan`
- **When** the scaffold runs through its CLI
- **Then** the skill carries `backends: [rocm, vulkan]` and `os: [linux]`
- **Test:** `tests/test_engine_skill_scaffold.py::test_scaffold_accepts_explicit_backends_and_slugs_a_dotted_engine_id`

### Requirement: the scaffold body names where the `os:` value came from

The scaffolded `SKILL.md` MUST state, in its own to-do list, the `os:` value it wrote AND the backend
evidence behind it, so the implementer can verify it against the pinned repo instead of guessing.

WHEN the scaffold writes a skill
THEN its body names the `os:` value and the registry evidence that produced it.

#### Scenario: the body carries the derivation

- **Given** a Metal-only engine and a CUDA/CPU engine in the registry
- **When** the scaffold runs for both
- **Then** the Metal body states `os: [darwin]` came from the backend list naming `Metal` and no Linux
  backend
- **And** the Linux body states `os: [linux]` came from the backend list naming no `Metal`
- **And** both say to check the value against the pinned repo
- **Test:** `tests/test_engine_skill_scaffold.py::test_the_scaffold_body_names_where_the_os_value_came_from`
