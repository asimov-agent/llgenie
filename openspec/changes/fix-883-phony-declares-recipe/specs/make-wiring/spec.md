# make-wiring

## ADDED Requirements

### Requirement: every `.PHONY` entry names a target that can run

A `.PHONY` entry MUST name a target that does something: a target with a recipe, an inline `;`
command, or at least one prerequisite (a declared alias). A key whose target does not exist, or
whose target has neither a recipe nor a prerequisite, MUST be an error that names it — `make <name>`
then prints `Nothing to be done` and exits 0, a green no-op that verifies nothing. Every offender
MUST be reported in one pass, and the report MUST separate "no target" from "runs nothing" so the
fix can be read off the message.

WHEN a `.PHONY` key is declared whose recipe is gone, or whose target runs nothing
THEN `make check-wiring` fails, naming every such key.

#### Scenario: a `.PHONY` key with no target fails, and deleting it is the fix

- **Given** a checkout whose `.PHONY` block names `ci-scope-phantom`, and no target of that name
- **When** the wiring is checked
- **Then** it exits non-zero, names `ci-scope-phantom`, and says `make` would print "Nothing to be done"
- **And** real `make ci-scope-phantom` runs nothing and exits 0, which is why the gate must catch it
- **And** removing the key from `.PHONY` makes the check pass
- **Test:** `tests/test_wiring.py::test_a_phony_entry_with_no_target_fails_and_deleting_it_is_the_fix`

#### Scenario: every unrunnable key is reported in one pass

- **Given** a `.PHONY` block naming a key with no target and a target with no recipe and no prerequisite
- **When** the wiring is checked
- **Then** both are named in the same output, each with the fix that matches its shape
- **Test:** `tests/test_wiring.py::test_every_unrunnable_phony_entry_is_reported_in_one_pass`

#### Scenario: a declared alias is a runnable `.PHONY` entry

- **Given** `.PHONY` entries whose goal line carries prerequisites, or an inline `;` command, instead of a recipe
- **When** the wiring is checked
- **Then** neither shape is an offender, because `make` runs the prerequisites or the inline command
- **Test:** `tests/test_wiring.py::test_a_declared_alias_is_a_runnable_phony_entry`

#### Scenario: the real tree declares no `.PHONY` entry it cannot run

- **Given** the real checkout's Makefiles
- **When** the reverse `.PHONY` direction is applied to the derived graph
- **Then** no key names a missing target and no key names a target that runs nothing
- **And** every declared key resolves to a target with a recipe, an inline command or a prerequisite
- **Test:** `tests/test_wiring.py::test_the_real_tree_declares_no_phony_entry_it_cannot_run`
