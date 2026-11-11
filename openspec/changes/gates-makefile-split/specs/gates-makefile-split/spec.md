# Gates-domain Makefile split

## ADDED Requirements

### Requirement: the gate targets live behind `include mk/gates.mk` with identical recipes

The top `Makefile` keeps the shared environment, `.PHONY`, `version`/`help` and `include mk/gates.mk`;
the gates-domain targets (`bash-check`, `check-host-space`, `reclaim-tmp-worktrees`, every
`check-*`, `*-report`, `git-identity-*`, `openspec-*`, `lint`, `lint-fix`) live in `mk/gates.mk`,
byte-for-byte identical to the pre-split file. A change to the gates domain touches one small file.

#### Scenario: the target surface is unchanged after the split

Given the current tree on the split branch with `mk/gates.mk` present and included,
when `make -qp` and `make help` are run,
then the target list is identical to the pre-split tree (`make -qp` diff empty) and
`make help` is byte-identical.

### Requirement: Makefile-text readers resolve the includes so the split does not blind a gate

Every gate that reads the Makefile text to find targets, help lines or phony declarations must
resolve `include mk/*.mk` (top Makefile + the included domain files, in include order) before
building its view — `check-wiring`, `check-docs`, `architecture-bot`'s census,
`check-dispatch-forms`, `issue-bot-gates` and the test suite's `makefiles_text`.

#### Scenario: a moved gate target stays visible to its reader

Given a gate-domain target (e.g. `lint`, `check-wiring`, `check-pr-hygiene`) moved behind
`include mk/gates.mk`,
when the corresponding Makefile-text reader runs against the split tree,
then the target is still found (the gate passes and reports the same result as before the split).

#### Scenario: a `.PHONY` name and a `make help` line for a moved target still resolve

Given a moved gate target whose `.PHONY` declaration and `##` help line are consulted by a reader,
when the reader runs,
then the declaration and the help line are still found (no "not a target in the Makefile" false red).

### Requirement: parity holds order and content for the wiring and documentation gates

`make check-wiring` and `make check-docs` report the same verdict and counts before and after the
split (`make -qp` targets, CI-reached targets, user-facing `##` targets all unchanged).

#### Scenario: check-wiring reports identically pre- and post-split

Given the pre-split tree and the split tree,
when `make check-wiring` runs against each,
then the output is identical (371 make targets, CI calls 130 of them).

#### Scenario: check-docs reports identically pre- and post-split

Given the pre-split tree and the split tree,
when `make check-docs` runs against each,
then the output is identical (337 user-facing targets documented).
