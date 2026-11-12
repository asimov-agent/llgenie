# Spec Delta: engine-selection-canonical

## ADDED Requirements

### Requirement: The fleet pin gate names every unpublished cell with its canonical engine id

`make check-engine-pins-published ALL=1` SHALL emit one machine-readable line per unpublished
committed cell in the form `[select] <engine-id> <variant> <tag>`, where `<engine-id>` is the id
from the committed params file — dots and other package-illegal characters intact — and `<tag>`
is the committed full tag string (`<pin8>-<hash8>-<variant>`). The ghcr URL line remains the
human-readable form; the `[select]` line is the contract other steps consume.

#### Scenario: dotted engine ids keep their dots in the selection lines

- **Given** a committed engine `llama.cpp` with cell `cpu` whose tag is unpublished
- **When** `make check-engine-pins-published ALL=1` reports the cell
- **Then** the output contains `[select] llama.cpp cpu <tag>`
- **And** no `[select]` line carries the package spelling `llama-cpp`

#### Scenario: published cells name no selection

- **Given** a committed cell whose tag resolves in ghcr
- **When** the ALL=1 sweep reports it as `PUBLISHED`
- **Then** no `[select]` line is emitted for it

### Requirement: The registry-liveness dispatch consumes only the selection contract

The registry-liveness dispatch step SHALL build every `gh workflow run engine-build.yml`
invocation's `engine=` and `arch=` inputs only from `[select]` lines of the fleet gate's own
output. It SHALL NOT reconstruct an engine id from a ghcr package URL. When the gate is red but
the output carries no `[select]` line, the step SHALL print the gate output and exit 0 — the
fleet step already reddens the run, and a dispatch that cannot name a cell must not fail twice.

#### Scenario: a dotted cell gets dispatched with its committed id

- **Given** the fleet gate names `[select] llama.cpp vulkan 7d7f0287-221a5e64-vulkan`
- **When** the dispatch step runs
- **Then** it dispatches `engine-build.yml` with `engine=llama.cpp` and `arch=vulkan` and `push=true`
- **And** no dispatch carries an engine id derived from a package name

### Requirement: An explicit engine or arch selection never resolves to the placeholder row

`python3 scripts/engine_image.py matrix` with an explicit `--engine` and/or `--arch` that matches
zero committed cells SHALL exit non-zero naming the unresolved selection: a no-such-engine verdict
names the requested id, and a no-such-variant verdict names the engine and its committed variants.
The synthesized `engine: "none"` placeholder row SHALL remain ONLY when no engine and no arch
selection narrowed the sweep to nothing (the `--changed` nothing-moved case, the whole-fleet case)
— the documented no-op GitHub needs to keep a matrix legal. Consequently `make engine-build-matrix
ENGINE=<typo>` and `make build-engines ENGINE=<typo>` are red, not green no-ops.

#### Scenario: package spelling is not an engine id

- **Given** committed params ids `llama.cpp`, `vllm`, … and no engine named `llama-cpp`
- **When** `make engine-build-matrix ENGINE=llama-cpp` runs
- **Then** the command exits non-zero
- **And** the error names `llama-cpp` as matching no committed engine id

#### Scenario: variant not committed for a real engine

- **Given** engine `llama.cpp` whose committed variants do not include `metal`
- **When** `matrix --json --ci --engine llama.cpp --arch metal` runs
- **Then** it exits non-zero naming `llama.cpp` and `metal`

#### Scenario: unscoped nothing-moved sweep keeps the placeholder no-op

- **Given** a `--changed` sweep against a base whose published tags already equal the tree's
- **When** `matrix --json --ci --changed <base>` runs
- **Then** it exits 0 with exactly the single placeholder row `{"engine": "none", …}`

#### Scenario: scoped dispatch builds the exact cell it names

- **Given** engine `llama.cpp` with committed variant `cpu`
- **When** `make engine-build-matrix ENGINE=llama.cpp ARCH=cpu` runs
- **Then** it exits 0 with exactly one include row whose engine is `llama.cpp` and variant is `cpu`
