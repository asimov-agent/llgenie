# pr-commit-authors

## ADDED Requirements

### Requirement: A PR's commits are authored by an allowed identity

`make check-pr-authors` SHALL fail when a non-merge commit in the PR's range is authored by a name
that is not exactly `Andy Holst` or `Asimov Agent`, or by a name whose email is not the one that
belongs to it. The range SHALL be the commits the PR ADDS (`git rev-list --no-merges <base>..<head>`),
so a commit already reachable from the base branch SHALL NOT be reported and a merge commit SHALL NOT
be reported. The finding SHALL name the commit, its author and the identity to set.

#### Scenario: a commit authored `andyholst`

- **GIVEN** a real git repository whose `main` is the base and a branch that adds one commit authored
  `andyholst <andy.holst@protonmail.com>`
- **WHEN** `check_pr_authors.py check --base main --head HEAD` runs
- **THEN** it SHALL exit non-zero and name the offending commit's author as `andyholst`
- **Test:** `tests/test_pr_authors.py::test_a_commit_authored_andyholst_is_a_violation`

#### Scenario: a commit authored `Andy`

- **GIVEN** a branch whose commit is authored `Andy <andy.holst@protonmail.com>`
- **WHEN** the guard reads it
- **THEN** it SHALL report the author `Andy` as outside the allowlist
- **Test:** `tests/test_pr_authors.py::test_a_commit_authored_andy_is_a_violation`

#### Scenario: a commit authored `Mr. Asimov`

- **GIVEN** a branch whose commit is authored `Mr. Asimov <support@docondee.com>`
- **WHEN** the guard reads it
- **THEN** it SHALL report the author as outside the allowlist
- **Test:** `tests/test_pr_authors.py::test_a_commit_authored_mr_asimov_is_a_violation`

#### Scenario: the allowed identities

- **GIVEN** a branch whose commits are authored `Andy Holst <andy.holst@protonmail.com>` and
  `Asimov Agent <support@docondee.com>`
- **WHEN** the guard reads it
- **THEN** it SHALL report no violation
- **Test:** `tests/test_pr_authors.py::test_the_allowed_identities_pass`

#### Scenario: the right name with the wrong email

- **GIVEN** a commit authored `Andy Holst <someone@else.example>`
- **WHEN** the guard reads it
- **THEN** it SHALL report the commit, because the name must carry the email that belongs to it
- **Test:** `tests/test_pr_authors.py::test_the_right_name_with_the_wrong_email_is_a_violation`

### Requirement: A commit's `Co-authored-by:` trailer is an allowed identity too

The guard SHALL read every `Co-authored-by: Name <email>` trailer in each commit's message and SHALL
fail when the co-author's name is not exactly `Andy Holst` or `Asimov Agent`, or its email is not the
one that belongs to that name. The finding SHALL be its own key, separate from the author finding, so a
commit whose author is allowed and whose co-author is not is reported once and unambiguously.

#### Scenario: an allowed author with an off-list co-author

- **GIVEN** a commit authored `Andy Holst <andy.holst@protonmail.com>` whose message carries
  `Co-authored-by: Mr. Asimov <support@docondee.com>`
- **WHEN** the guard reads it
- **THEN** it SHALL report the co-author under its own key and SHALL NOT report the author
- **Test:** `tests/test_pr_authors.py::test_an_off_list_co_author_is_its_own_finding`

#### Scenario: an allowed co-author is accepted

- **GIVEN** a commit authored `Andy Holst <andy.holst@protonmail.com>` whose message carries
  `Co-authored-by: Asimov Agent <support@docondee.com>`
- **WHEN** the guard reads it
- **THEN** it SHALL report no violation
- **Test:** `tests/test_pr_authors.py::test_an_allowed_co_author_is_accepted`

### Requirement: A commit already reachable from the base branch is out of scope

The guard SHALL read only the commits the PR adds. A commit reachable from the base branch SHALL NOT be
reported, and a merge commit SHALL NOT be reported, so the gate cannot fail on history the PR did not
create — the merge commit GitHub writes on `main` is authored `GitHub <noreply@github.com>`.

#### Scenario: an off-list commit on the base branch

- **GIVEN** a base branch that carries a commit authored `Mr. Asimov <support@docondee.com>`, and a
  head branch that adds one allowed commit on top of it
- **WHEN** the guard reads the head's range against the base
- **THEN** it SHALL report no violation, because the off-list commit is on the base, not in the range
- **Test:** `tests/test_pr_authors.py::test_a_commit_on_the_base_branch_is_not_reported`

#### Scenario: a merge commit in the range

- **GIVEN** a head branch whose tip is a merge commit
- **WHEN** the guard reads the range
- **THEN** the merge commit SHALL NOT be reported, even though its author is not an allowed identity
- **Test:** `tests/test_pr_authors.py::test_a_merge_commit_is_not_reported`

### Requirement: The repository's own producers assign an allowed identity

The guard SHALL read every file the repository owns that can author a commit — `.github/workflows/*.yml`,
the `Makefile` and `scripts/**` — and SHALL fail when one assigns a literal git identity outside the
allowlist. A producer whose identity resolves at run time SHALL be reported in `report` and SHALL NOT
be a violation.

#### Scenario: a workflow that commits as a literal off-list identity

- **GIVEN** a fixture tree whose workflow sets `user.name` to `llgenie fix-bot`
- **WHEN** the guard reads it
- **THEN** it SHALL report the producer
- **Test:** `tests/test_pr_authors.py::test_a_producer_with_an_off_list_identity_is_a_violation`

#### Scenario: a producer whose identity resolves at run time

- **GIVEN** a fixture tree whose workflow assigns the identity from `$(gh api user --jq .login)`
- **WHEN** the guard reads it
- **THEN** it SHALL NOT report a violation
- **Test:** `tests/test_pr_authors.py::test_a_runtime_identity_is_accepted`

#### Scenario: an unquoted `GIT_AUTHOR_NAME:` env assignment

- **GIVEN** a fixture tree whose workflow carries `GIT_AUTHOR_NAME: Asimov Agent` — an ALLOWED
  identity, unquoted, as YAML needs no quotes for a space
- **WHEN** the guard reads it
- **THEN** it SHALL read the value to the end of the line and report NO violation, rather than
  reading the bare token `Asimov` and flagging an allowed identity
- **Test:** `tests/test_pr_authors.py::test_an_unquoted_env_identity_reads_whole`

#### Scenario: an unquoted off-list env assignment

- **GIVEN** a fixture tree whose workflow carries `GIT_AUTHOR_NAME: github-actions[bot]` unquoted
- **WHEN** the guard reads it
- **THEN** it SHALL report the env name and its email as violations
- **Test:** `tests/test_pr_authors.py::test_an_unquoted_env_identity_that_is_off_list_is_a_violation`

#### Scenario: the guard's own source is not a producer

- **GIVEN** `scripts/check_pr_authors.py`, which NAMES identities as data in its docstring, its
  regexes and the remediation text a finding carries, and would match its own assignment patterns
- **WHEN** the guard enumerates the files it governs
- **THEN** its own file SHALL NOT be among them, so the words it prints as remediation are never
  reported as a violation of the rule it enforces
- **Test:** `tests/test_pr_authors.py::test_the_guard_does_not_flag_its_own_source`

### Requirement: AGENTS.md states the rule, and the exit code is what CI gates on

`AGENTS.md` SHALL carry the section that states the rule, so deleting it is a red gate rather than a
silent edit. `make check-pr-authors` SHALL run inside `ci-unit`, and `main(["check"])` SHALL return
non-zero on a violation and 0 on this repository's tree.

#### Scenario: the rule is removed from AGENTS.md

- **GIVEN** a fixture tree whose `AGENTS.md` does not carry the section
- **WHEN** the guard reads it
- **THEN** it SHALL report `agents-mandate`
- **Test:** `tests/test_pr_authors.py::test_a_missing_agents_mandate_is_a_violation`

#### Scenario: the exit code contract

- **GIVEN** a fixture tree with an off-list author and this repository's tree
- **WHEN** `main(["check"])` runs against each
- **THEN** it SHALL return non-zero for the fixture and 0 for this repository
- **Test:** `tests/test_pr_authors.py::test_check_exits_non_zero_on_a_violation_and_zero_on_this_repo`

#### Scenario: this repository passes its own gate

- **GIVEN** this repository at its current tip
- **WHEN** the guard reads its producers and its `AGENTS.md`
- **THEN** it SHALL report no violation, because a convention the repository violates is not a
  convention
- **Test:** `tests/test_pr_authors.py::test_this_repository_passes_its_own_gate`

### Requirement: Every spec scenario carries Given / When / Then and a test

Every scenario in this spec SHALL state a GIVEN, a WHEN and a THEN, and SHALL name the test that proves
it, so a scenario cannot exist without a test and a test cannot exist without a scenario.

#### Scenario: the spec is complete

- **GIVEN** this spec file
- **WHEN** every scenario in it is read
- **THEN** each one SHALL carry GIVEN/WHEN/THEN and a `Test:` line naming an existing test
- **Test:** `tests/test_pr_authors.py::test_every_spec_scenario_has_given_when_then_and_a_test`
