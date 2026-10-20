# wiring-guard

## ADDED Requirements

### Requirement: Every target that produces no file of its own name is declared `.PHONY`

`scripts/check_wiring.py` SHALL fail when a parsed make target (in `Makefile` or `tools/Makefile`) is
neither declared in that Makefile's `.PHONY:` block nor recorded under `not_phony` in
`tests/fixtures/host-only-wiring.json`. A recorded entry SHALL carry a reason and a date, and SHALL be
refused as stale once the target is declared `.PHONY` or no longer exists.

WHEN a target's recipe is reached by `make`
THEN no file named after it shadows it, because the target is `.PHONY` (or its file-producing nature is
a dated decision).

#### Scenario: an undeclared target is a green no-op

Given a checkout whose target is not declared `.PHONY`,
When  a file carrying the target's name exists in that checkout and `make <target>` runs,
Then  no recipe runs and make reports success — and `make check-wiring` fails, naming the target.

- **Test:** `tests/test_wiring.py::test_an_undeclared_target_runs_nothing_and_the_guard_catches_it`

#### Scenario: declaring the target fixes both

Given the same checkout after the target joins the `.PHONY:` block,
When  `make <target>` runs and `make check-wiring` is checked,
Then  the recipe runs and the guard reports no error.

- **Test:** `tests/test_wiring.py::test_an_undeclared_target_runs_nothing_and_the_guard_catches_it`

#### Scenario: a target that produces a file of its own name is a dated decision

Given a target whose recipe writes a file with the target's own name,
When  it is recorded under `not_phony` with a reason and a date,
Then  `make check-wiring` passes without it being declared `.PHONY`.

- **Test:** `tests/test_wiring.py::test_a_target_that_produces_a_file_of_its_name_is_recorded_not_phony`

#### Scenario: a not_phony decision cannot rot

Given a `not_phony` entry,
When  the target is declared `.PHONY` (or the target no longer exists), or the entry has no reason,
Then  `make check-wiring` fails and says which one it is.

- **Test:** `tests/test_wiring.py::test_a_target_that_produces_a_file_of_its_name_is_recorded_not_phony`

#### Scenario: the repository itself obeys the rule

Given the real checkout,
When  `make check-wiring` runs,
Then  every parsed target is declared `.PHONY` or recorded, and the roster is derived from the
      Makefiles rather than listed by hand.

- **Test:** `tests/test_wiring.py::test_the_real_tree_declares_every_target_phony`
  (the gate: `make check-wiring`, inside `make ci-unit`)
