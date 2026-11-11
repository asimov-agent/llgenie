# Force-phrase instruction drift — the agent surface must teach the canonical push vehicle

## ADDED Requirements

### Requirement: the instruction surface teaches `--force-if-includes` only in its ancestor case

Every occurrence of `--force-if-includes` in the instruction surface — `agents/**/SKILL.md`,
`agents/**/references/**`, `agents/**/prompts/**`, excluding the `llgenie-pr-merge-conflict` lane
(which carries the canonical #1960 wording) — must carry an explicit qualification: the same line or
a line within ±2 names the ancestor/amend/integrate case, or teaches the flag's rejection. A stale
occurrence presents the flag as the general vehicle for pushing a rebased, squashed, or otherwise
rewritten head.

#### Scenario: a stale tuple in a lane reference

Given a file under `agents/<lane>/skills/.../references/` containing the line
`git push --force-with-lease --force-if-includes origin <branch>` with no ancestor/amend/rejection
qualification within ±2 lines
When the hygiene test scans the instruction surface
Then the test reports that file:line as a drift finding
And `make test-unit` exits non-zero

#### Scenario: the same command carries its qualification

Given a file in the instruction surface containing `--force-if-includes` whose line (or a line within
±2) names the ancestor/amend/integrate case or the flag's rejection
When the hygiene test scans the instruction surface
Then no finding is raised for that occurrence

#### Scenario: the planted fixture reds the check

Given the committed fixture `tests/fixtures/force_phrase_instruction_surface/` which plants one
unqualified stale-tuple line and one qualified line
When the hygiene test scans the fixture surface
Then exactly the planted unqualified file:line is reported and the qualified one is not
And the test proves the check cannot pass vacuously

#### Scenario: the live surface is clean after adjudication

Given the repo tree after the #2502 adjudication (36 corrected sites, 10 qualified keeps, 9 keeps)
When `make test-unit` runs the discovered hygiene test against the live `agents/` surface
Then the test passes with zero findings (an empty allow-list is valid)

### Requirement: adjudication is recorded

Every surface hit at measurement time carries a verdict (corrected / kept-qualified / kept) recorded
in this change's proposal, so a later reader can tell a deliberate keep from an oversight.

#### Scenario: a kept hit is traceable

Given a file:line that keeps `--force-if-includes`
When a reviewer consults the change proposal's adjudication table
Then the entry names the verdict and the qualification basis

- **Test:** tests/test_force_phrase_instruction_surface.py (unit-lane discovery via scripts/unit_tests.py)
