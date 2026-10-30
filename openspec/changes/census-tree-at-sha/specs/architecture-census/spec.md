## ADDED Requirements

### Requirement: census-referent-is-the-named-tree

`make check-architecture-census` SHALL treat the `measured at <sha>` commit named by
`docs/ARCHITECTURE.md` as the referent of every census claim, SHALL require that commit to be an
ancestor of `HEAD`, and SHALL compare each stated count with `git ls-tree -r --name-only <sha>` at
that commit rather than at `HEAD`.

#### Scenario: a branch that adds files keeps the census valid

- **Given** a branch whose `docs/ARCHITECTURE.md` census was measured at a commit that is an ancestor of its head
- **And** the branch adds files after that commit and does not edit the doc
- **When** `python3 scripts/check_architecture_census.py check` runs
- **Then** it exits 0 and reports the pointer it measured, not `HEAD`
- **Test:** `tests/test_architecture_census.py::test_a_branch_that_adds_files_does_not_have_to_move_the_census`

#### Scenario: a stale number at the named sha reds naming both values

- **Given** a doc whose stated number for a counted directory disagrees with the tree at its own pointer
- **When** the gate runs
- **Then** it exits non-zero, naming what the doc states and what the tree at that sha states
- **Test:** `tests/test_architecture_census.py::test_a_stale_number_reds_naming_the_claim`

#### Scenario: a non-ancestor pointer reds naming the sha

- **Given** a pointer naming a real commit that is not an ancestor of `HEAD`
- **When** the gate runs
- **Then** it exits non-zero and names the sha as not an ancestor of `HEAD`
- **Test:** `tests/test_architecture_census.py::test_a_pointer_to_a_non_ancestor_commit_reds_naming_it`

#### Scenario: a dangling pointer reds

- **Given** a pointer naming a sha that exists nowhere in the repository
- **When** the gate runs
- **Then** it exits non-zero and says the commit is not real
- **Test:** `tests/test_architecture_census.py::test_a_dangling_pointer_reds`

#### Scenario: a doc with no pointer reds

- **Given** a census with no `measured at <sha>` pointer
- **When** the gate runs
- **Then** it exits non-zero and names `docs/ARCHITECTURE.md` and the absent pointer
- **Test:** `tests/test_architecture_census.py::test_a_doc_with_no_pointer_reds`

#### Scenario: the gate still runs with the docs gate

- **Given** `make check-docs` is the docs gate
- **When** `check-docs` runs
- **Then** `scripts/check_architecture_census.py check` runs as part of it
- **Test:** the `check-docs` recipe in `Makefile` invokes `check_architecture_census.py check`
