# engine-selection-canonical

## ADDED Requirements

### Requirement: the fleet gate emits a canonical per-cell dispatch line with dots intact

`make check-engine-pins-published ALL=1` MUST print, for every unpublished committed engine cell,
a machine-readable line `[select] <engine-id> <variant> <tag>` on its own line, where `<engine-id>`
is the committed params id exactly as committed (dots preserved, e.g. `llama.cpp`) and `<tag>` is
the exact image tag. The package spelling (dots replaced by dashes: `llama-cpp`) MUST NOT appear as
an engine id in any of these lines.

WHEN the committed fleet is swept with `ALL=1` and a dotted-id cell is unpublished,
THEN the sweep prints `[select] llama.cpp <variant> <tag>` for that cell, never a dashed `llama-cpp`.

#### Scenario: an unpublished dotted cell is named canonically

- **Given** a committed engine with a dotted params id (`llama.cpp`) whose exact tag is unpublished
- **When** `check_engine_pins_published.py check --all` prints the missing cells
- **Then** the dispatch line carries the committed id `llama.cpp`, never the dashed `llama-cpp`
- **Test:** `tests/test_check_engine_pins_published.py::test_all_sweep_emits_canonical_select_line_with_dots_intact`

### Requirement: the registry-liveness dispatch consumes only the canonical select lines

The registry-liveness dispatch step MUST build its `gh workflow run engine-build.yml` inputs
(`engine` / `arch`) only from the `[select] <engine-id> <variant> <tag>` lines the fleet gate emits.
The step MUST NOT reconstruct an engine id from a GHCR package URL. `variant` is the arch segment of
the committed tag, dispatched as `-f arch=<variant>`.

WHEN a scoped dispatch is issued for a missing dotted cell,
THEN `engine-build.yml` is invoked with `-f engine=llama.cpp` (dots intact)
and a real build job named `engine-build-llama.cpp-*` runs — never a `none` placeholder no-op.

#### Scenario: dispatch derives inputs from select lines only

- **Given** the `registry-liveness.yml` dispatch step and the fleet gate output
- **When** a dotted cell is missing
- **Then** the step greps `^\[select\]`, reads `$2` (engine id) and `$3` (variant), and dispatches
  `-f engine='$engine' -f arch='$variant' -f push=true`; no engine id is carved out of a package URL
- **Test:** `tests/test_check_engine_pins_published.py::test_dispatch_consumes_only_select_lines_never_package_urls`

### Requirement: an explicit selection that resolves to zero committed cells fails loudly

`scripts/engine_image.py matrix()` MUST exit non-zero, naming the unresolved selection, when an
explicit `--engine` (or `--engine`+`--arch`) selection resolves to zero committed cells. This
includes a package spelling (`--engine llama-cpp` → "no committed engine id `llama-cpp`") and a
known id with a non-variant arch (`--engine llama.cpp --arch metal` → "`llama.cpp` has no committed
variant `metal`"). The `none` placeholder row MUST remain ONLY for the unscoped sweep — `--changed`
with nothing moved, and whole-fleet sweeps with no `--engine`/`--arch`. This makes
`make engine-build-matrix ENGINE=<typo>` and `make build-engines ENGINE=<typo>` fail instead of
silently building nothing.

WHEN `matrix --engine <unknown-id>` (or a known id with an unknown variant) is run,
THEN it prints the unresolved selection name and exits non-zero; unscoped/`--changed` sweeps still
return the placeholder.

#### Scenario: a package spelling is a loud error, not a no-op

- **Given** the committed params and an explicit selection of `llama-cpp` (the package spelling)
- **When** `matrix --engine llama-cpp --arch cpu` runs
- **Then** it prints `no committed engine id \`llama-cpp\`` and exits 1
- **Test:** `tests/test_engine_image_matrix.py::test_package_spelling_of_dotted_id_is_a_loud_error`

#### Scenario: a known id with a non-variant arch is a loud error

- **Given** the committed `llama.cpp` params
- **When** `matrix --engine llama.cpp --arch metal` runs
- **Then** it prints that `llama.cpp` has no committed variant `metal` and exits 1
- **Test:** `tests/test_engine_image_matrix.py::test_known_engine_with_unknown_variant_fails_loudly`

#### Scenario: the unscoped sweep keeps the placeholder no-op

- **Given** a committed tree with nothing moved
- **When** `matrix --ci --changed <self>` (or a whole-fleet sweep with no engine/arch) runs
- **Then** it returns the single `none` placeholder row and exits 0
- **Test:** `tests/test_engine_image_matrix.py::test_unscoped_sweep_still_returns_the_placeholder`
