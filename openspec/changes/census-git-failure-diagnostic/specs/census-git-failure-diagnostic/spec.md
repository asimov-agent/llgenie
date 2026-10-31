# census-git-failure-diagnostic

## ADDED Requirements

### Requirement: an unreadable checkout is not a document defect

The gate MUST distinguish "git could not read this checkout" from "the document names a bad
commit", and MUST decide from the git call's own failure, never by guessing at the document. When
the checkout is unreadable — `git rev-parse --git-dir` fails or raises, or its stderr names a
git-environment failure (`not a git repository`, `dubious ownership`, a missing `git`) — `check()`
MUST emit a finding whose message names the checkout / git as the failing side (an `UNREADABLE`
finding) and MUST exit **2** (distinct from `1` = a real census defect, from `0` = OK), so a check
that could not run never reads as clean. The exit codes MUST be documented in the module docstring
and asserted by tests.

#### Scenario: no repository is reported as an unreadable checkout, not a bad pointer

- **Given** a directory that contains `docs/ARCHITECTURE.md` but no git repository
- **When** the gate's `check()` runs there
- **Then** the output names the checkout / git (an `UNREADABLE` finding), does NOT name the document's
  pointer as `not a real commit`, and the exit code is 2
- **Test:** `tests/test_architecture_census.py::test_an_unreadable_checkout_is_unreadable_not_a_bad_pointer`

#### Scenario: an unreadable checkout exits 2

- **Given** the same unreadable checkout (no runnable `git rev-parse --git-dir`)
- **When** the gate runs
- **Then** its exit code is 2, distinct from both the OK exit 0 and the census-defect exit 1
- **Test:** `tests/test_architecture_census.py::test_an_unreadable_checkout_is_unreadable_not_a_bad_pointer`

### Requirement: a genuinely bad pointer still fails with the old message

When git runs and the sha truly does not resolve, the gate MUST keep today's finding — the message
that names the pointer as `not a real commit` — and exit 1. The "(dangling from an amend?)"
speculation MUST be dropped from that message. A full, readable clone whose census matches the tree
MUST exit 0 and print `OK`.

#### Scenario: a bad pointer in a readable repo still fails naming it

- **Given** a readable repo whose census names a sha that resolves to no commit
- **When** the gate runs
- **Then** the output names the pointer as `not a real commit` and the exit code is 1
- **Test:** `tests/test_architecture_census.py::test_a_dangling_pointer_reds` (the existing test, kept)

#### Scenario: a clean full clone passes

- **Given** a full clone whose ARCHITECTURE census matches the tree at its `measured at <sha>`
- **When** the gate runs
- **Then** it prints `OK` and exits 0
- **Test:** `tests/test_architecture_census.py::test_a_branch_that_adds_files_does_not_have_to_move_the_census` (existing, kept)
