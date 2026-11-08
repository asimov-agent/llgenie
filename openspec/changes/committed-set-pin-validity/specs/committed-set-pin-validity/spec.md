# committed-set-pin-validity

## ADDED Requirements

### Requirement: the committed-set sweep fails when a committed engine tag resolves no manifest

`check_engine_pins_published.py check --all` MUST probe the exact tag of EVERY committed enabled
engine cell (all backends, derived from the params matrix — the `committed_cells` set) and exit 1 when
ANY of those tags resolves no manifest, so a committed pin whose image was never rebuilt cannot sit
silently on `main` (`tensorfold/cuda@ef27f74f`, issue #2190).

WHEN `check --all` is run AND some committed enabled cell's exact tag returns `manifest unknown`
THEN it exits 1, names each unresolved tag, and prints a `dispatch engine-build with push=true` hint;
when every committed cell's tag resolves, it exits 0.

#### Scenario: a committed cell whose tag 404s reds the sweep

- **Given** the committed set contains a cell whose exact tag returns HTTP 404 from the registry
- **When** `check_committed()` runs over that set
- **Then** it exits 1 and names the unresolved ref
- **Test:** `tests/test_check_engine_pins_published.py::test_committed_red_when_a_committed_tag_is_absent`
  stubs the digest probe to 404 the exact committed tag and asserts `rc == 1` with the ref named

### Requirement: the same committed tag green once published

A committed cell whose exact tag resolves a manifest must make the identical sweep pass — the guard
must be toggled by the registry answer, not by which engine is in the set.

WHEN `check --all` is run AND every committed cell's exact tag resolves a manifest
THEN it exits 0.

#### Scenario: a committed cell resolves green

- **Given** the committed set contains a cell whose exact tag resolves a manifest
- **When** `check_committed()` runs over that same set
- **Then** it exits 0
- **Test:** `tests/test_check_engine_pins_published.py::test_committed_green_when_the_same_committed_tag_resolves`
  stubs the digest probe to resolve the exact committed tag and asserts `rc == 0`

### Requirement: the sweep covers every non-disabled committed cell

The committed set MUST enumerate every `(engine, variant)` cell the params matrix declares buildable —
all backends, disabled cells excluded — because a gap hidden in a backend no PR touches is exactly the
class #2190 caught.

WHEN the committed set is enumerated
THEN it contains one `(engine, variant)` per committed non-disabled cell, including non-cuda backends,
and excludes every disabled cell.

#### Scenario: enumeration covers all-backend cells and skips disabled ones

- **Given** the committed params matrix
- **When** `committed_cells()` enumerates it
- **Then** all-backend cells (e.g. `sglang`/`rocm`) are present and every disabled cell is absent
- **Test:** `tests/test_check_engine_pins_published.py::test_committed_sweeps_every_non_disabled_cell`
  asserts membership plus the disabled-skip

### Requirement: the sweep has a runnable gate and is .PHONY

The committed-set sweep MUST be invocable as its own make target (`check-engine-pins-valid` invoking
`check --all`) and be `.PHONY`-declared, so a maintainer or CI runs the class-wide sweep in one command.

WHEN `make check-engine-pins-valid` is invoked
THEN it runs `check --all` and the target is declared `.PHONY`.

#### Scenario: the make target is wired and .PHONY

- **Given** the Makefile
- **When** the gate wiring is read
- **Then** `check-engine-pins-valid` invokes `check --all` and is declared `.PHONY`
- **Test:** `tests/test_check_engine_pins_published.py::test_committed_wired_into_make_and_phony`
  asserts the target text and the `.PHONY` membership

### Requirement: the live registry sweep is a network-marked test

A test that sweeps the committed set against the REAL GHCR answers a question only CI can settle, so
it MUST be `@pytest.mark.network` (excluded from the hermetic gate by `-m "not network"`, issue
#1000).

WHEN the live sweep test runs in the network pipeline
THEN it calls `check_committed()` for real and asserts `rc == 0`.

#### Scenario: live GHCR sweep

- **Given** the real GHCR registry
- **When** `check_committed()` runs for real
- **Then** `rc == 0` when every committed cell is published
- **Test:** `tests/test_check_engine_pins_published.py::test_every_committed_engine_cell_tag_is_published_live` (network-marked)
