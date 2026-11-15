## ADDED Requirements

### Requirement: The test-suite Makefile domain lives in mk/tests.mk

The 18 host/user test-suite targets named by issue #2677 SHALL be declared in
`mk/tests.mk`, included from the top `Makefile`'s include block (appended after
`mk/bots.mk`), with target names, prerequisites, guard comments, recipes and `##` help
lines byte-identical to their pre-move text. The `ci-*` pipeline job targets SHALL stay
in `mk/ci.mk`.

#### Scenario: inventory survives the move

- **WHEN** `make -qp` runs before and after the move at the same commit's content
- **THEN** the declared-target sets are identical (the only new record is the include
  file itself), and the top `Makefile`'s declared-target count drops by exactly 18

#### Scenario: help output is unchanged

- **WHEN** `make help` runs before and after the move
- **THEN** the emitted help text is byte-identical

### Requirement: Moved targets stay discoverable to the include-aware readers

`scripts/unit_tests.py` roster claims and `scripts/check_wiring.py` wiring checks SHALL
resolve the moved targets through the include chain with no reader change.

#### Scenario: suite roster claims still resolve

- **WHEN** `python3 scripts/unit_tests.py check` runs against the moved tree
- **THEN** it exits 0 and every roster claim naming `make test-*` finds its recipe

#### Scenario: wiring gate stays green

- **WHEN** `make check-wiring` runs against the moved tree
- **THEN** it exits 0 and reports the make targets including the moved 18
