# close-set-completeness

## ADDED Requirements

### Requirement: a resolved issue must be closed or on-record justified-open

The gate MUST scan the PR body and the squash commit text for resolving references — a `#N` under
a fixing/resolving/completing/implementing/repairing verb with up to 24 lowercase letters between
the verb and `#N` — and MUST report a finding (`close-set/<n>`, severity RED) for each such issue
that is neither adjacently closed nor named in an on-record `does not close #N because <reason>`
justification. A close of a different issue does not satisfy it. A bare `see #9` reference and a
`## Not covered` remainder MUST NOT be findings. After application the `clos(e|es|ed|ing)` forms
MUST NOT be treated as resolving claims.

WHEN the body or joined commit text resolvingly names issue X and X is neither adjacently closed
nor on-record justified-open
THEN the check reports `close-set/<X>` and fails.

#### Scenario: names X + fixes X + closes only Y is red

- **Given** a body that adjacently closes `#1617` and resolvingly names `#1582` with no close or justification
- **When** `check_completeness` runs
- **Then** it reports `close-set/1582` and does not report `close-set/1617`
- **Test:** `tests/test_check_pr_closing.py::test_completeness__names_and_fixes_X_closes_only_Y_is_RED`

#### Scenario: closes both is green

- **Given** a body that adjacently closes both `#1582` and `#1617`
- **When** `check_completeness` runs
- **Then** it reports no finding
- **Test:** `tests/test_check_pr_closing.py::test_completeness__closes_both_is_GREEN`

#### Scenario: an on-record first-person does-not-close note is green

- **Given** a body carrying `We do not close #1582 because <reason>` and a justification reason
- **When** `check_completeness` runs
- **Then** it honours the first-person justification and reports no finding
- **Test:** `tests/test_check_pr_closing.py::test_completeness__first_person_justification_is_honoured`

#### Scenario: a bare reference is not a finding

- **Given** a body that mentions `see #9` with no resolving verb
- **When** `check_completeness` runs
- **Then** it reports no finding
- **Test:** `tests/test_check_pr_closing.py::test_completeness__bare_reference_is_not_a_finding`

### Requirement: a negated close is not a closing reference

`closing_references` MUST remove a negated close clause (`do not close #1582`, `does not close
#N`, `cannot close #N`, `didn't close #N`) entirely, so the `#N` it names cannot survive as an
adjacent closing reference and the squash/body close-set comparison sees the same set on both
sides.

WHEN a text says `We do not close #1582 because …`
THEN `closing_references` returns a set that does not include `#1582`.

#### Scenario: a negated close stays out of the close set

- **Given** the string `We do not close #1582 because it is out of scope.`
- **When** `closing_references` runs
- **Then** it returns `[]`
- **Test:** `tests/test_check_pr_closing.py::test_closing_references_drop_a_negated_close`
