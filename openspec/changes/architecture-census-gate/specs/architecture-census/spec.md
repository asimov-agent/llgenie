## ADDED Requirements

### Requirement: check-architecture-census

The tree SHALL provide a `make check-architecture-census` target that compares the census in
`docs/ARCHITECTURE.md` against the tree, and SHALL fail when the document omits or mistates a counted
claim that `git ls-tree -r --name-only HEAD` produces.

#### Scenario: clean tree passes and names the sha

- **Given** the census sentence and count cells in `docs/ARCHITECTURE.md` equal `git ls-tree` counts at `HEAD`
- **When** `make check-architecture-census` runs
- **Then** it exits 0 and prints the sha it measured
- **Test:** `make check-architecture-census` exits 0 and its output contains `measured at`

#### Scenario: a stale number fails and names both values

- **Given** one census number in `docs/ARCHITECTURE.md` disagrees with `git ls-tree` at `HEAD`
- **When** `make check-architecture-census` runs
- **Then** it exits non-zero, naming the tree count and the claim it could not find
- **Test:** edit a census number, observe a non-zero exit naming both values, restore it

#### Scenario: it runs with the docs gate

- **Given** `make check-docs` is the docs gate
- **When** `check-docs` runs
- **Then** `check_architecture_census.py` runs as part of it
- **Test:** `scripts/check_docs.py` lists or `check-docs`'s recipe invokes `check_architecture_census.py`
