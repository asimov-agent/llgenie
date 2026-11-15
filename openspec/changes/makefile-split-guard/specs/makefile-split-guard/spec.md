# Makefile split guard (wiring)

## ADDED Requirements

### Requirement: the wiring guard fails on a target declared twice across the includes

`scripts/check_wiring.py` collects declared target names per makefile in include order over
the resolved set (`Makefile` first, then every `mk/*.mk` its `include` directives name, in
directive order) and reports a finding for every target name declared in more than one file.
The finding names the target and BOTH files it is declared in, so the next PR that duplicates
a recipe is red instead of shipping a Makefile where make silently drops one recipe.

#### Scenario: a planted duplicate across two included files reds naming both files

Given a scratch checkout whose `Makefile` includes `mk/a.mk` and `mk/b.mk` and both declare a
target named `shared:`,
when `scripts/check_wiring.py check` runs against it,
then it exits 1 and the finding names `shared` and both `mk/a.mk` and `mk/b.mk`.

#### Scenario: the real tree declares no duplicate

Given the repository on `main`,
when the wiring guard computes declarations over `Makefile` + `mk/*.mk`,
then the duplicate set is empty and the check exits 0.

### Requirement: the line budget is one committed source and the guard enforces it

`tests/fixtures/makefile-line-budgets.json` is the single committed source of the budget: a
ceiling applied to every `mk/*.mk` file (600 at landing, the measured max being 499) and a
ratchet ceiling for the top `Makefile` recorded at the landing measurement (977), which may
decrease and never increases without a dated decision entry (reason + decided) in that file.
The guard fails on any file over its ceiling — naming the file, its actual line count and the
ceiling — and fails when the budget file is missing or malformed, so the enforcement cannot be
silently deleted.

#### Scenario: a planted over-budget file reds naming file and ceiling

Given a scratch checkout whose `mk/a.mk` exceeds the committed ceiling,
when the wiring guard check runs,
then it exits 1 with a finding naming `mk/a.mk`, its line count and the ceiling.

#### Scenario: removing the budget file reds the gate

Given a scratch checkout whose budget file has been deleted,
when the wiring guard check runs,
then it exits 1 naming the missing budget file.

#### Scenario: the tests derive the numbers, they do not bake them

Given the test suite asserts the real tree fits its budget,
when the committed ceilings or the file line counts change,
then the tests read the ceilings from the committed source and the measured counts from the
tree — a change to either flows through the tests without editing a test body, and baking a
number into a test is itself caught by reading the budget from the committed source.
