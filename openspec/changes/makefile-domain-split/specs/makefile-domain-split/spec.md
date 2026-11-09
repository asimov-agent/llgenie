# Makefile domain split — wiring

## MODIFIED Requirements

### Requirement: the wiring gate resolves `include mk/*.mk`

`scripts/check_wiring.py` builds its make-target graph from the top `Makefile`
AND every file it `include`s. It must follow `include mk/*.mk` directives
(any order) when building recipes, prerequisites, `.PHONY` and help lines, so
moving a target from `Makefile` to an included `mk/*.mk` does not make the
gate go blind.

#### Scenario: target moved into an included file stays wired

Given a target whose definition moves from the top `Makefile` into `mk/gates.mk`
When `check_wiring.py check` reads the tree
Then the target is still discovered as a make target
And a workflow that calls `make <target>` still resolves it
And the target's `##` help line still reaches `make help`

#### Scenario: duplicate target across includes is a finding

Given `mk/a.mk` declares a target and `mk/b.mk` declares the same name
When `check_wiring.py check` runs
Then it fails, naming the duplicated target and both files
(a duplicate target name across includes is a merge-conflict-class defect)

### Requirement: per-file line budget for `mk/*.mk`

Each `mk/*.mk` file carries a stated line budget that `check_wiring.py`
enforces, so a domain file cannot quietly grow back to Makefile size.

#### Scenario: a file within budget passes

Given every `mk/*.mk` file is within its stated line budget
When `check_wiring.py check` runs
Then it reports all budgets met

#### Scenario: a file over budget fails

Given a `mk/*.mk` file exceeds its stated line budget
When `check_wiring.py check` runs
Then it fails, naming the file, its line count and the budget

### Requirement: target names and behaviour are unchanged by the split

The split moves target definitions between files verbatim; it never renames a
target, reorders a recipe, changes a prerequisite, or alters a stage's logic.

#### Scenario: `make -qp` names the same targets

Given the repo before and after the split
When `make -qp` is parsed for target names
Then both lists are byte-identical, sorted
And `make help` output is byte-identical

#### Scenario: the five longest recipes are entry points

Given the five longest recipes (after `help`, which stays in the top Makefile)
When each is measured
Then each is `<= 3` lines
And each stage's logic lives in a `scripts/*.py` entry point with unit tests
