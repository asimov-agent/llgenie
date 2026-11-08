# acceptance-proven-awaiting-writer

## ADDED Requirements

### Requirement: the acceptance gate reports a proven-but-unticked criterion distinctly from an unproven one

`make check-pr-acceptance` MUST report an issue's unticked `## Acceptance criteria` criterion in one
of two distinct states: `acceptance-unchecked` (red) when the PR carries NO trusted approving review
verdict at the current head, or `acceptance-proven-awaiting-writer` (a distinct, non-red finding)
when the PR carries a trusted approve verdict — an ACCEPTING `bot_verdict` marker whose `head` equals
the PR's current head, authored by a repository or bot identity with `reviewer` equal to the author —
at that exact head. A `changes` verdict, a verdict for a different head, or an unreadable comment
trail MUST NOT be treated as evidence; the criterion stays `acceptance-unchecked` (red). The gate
MUST exit non-zero when any BLOCKING finding exists and zero when only `proven-awaiting-writer`
findings remain.

WHEN a PR that `closes #N` carries no trusted approve verdict at its head and issue `#N` has an
unticked criterion,
THEN the gate reports `acceptance-unchecked` (red, exit non-zero).

WHEN the same PR carries a trusted approve verdict at its current head,
THEN the gate reports `acceptance-proven-awaiting-writer` (distinct, non-red, exit zero)
AND never `acceptance-unchecked` for that criterion.

#### Scenario: an unproven box stays red

- **Given** a PR closing an issue whose `## Acceptance criteria` has an unticked `- [ ]` item
- **And** no trusted approve verdict comment exists on the PR at the current head
- **When** `make check-pr-acceptance` runs with `--pr <n>`
- **Then** it reports `acceptance-unchecked`
- **And** exits non-zero
- **Test:** `tests/test_check_pr_acceptance.py::test_unticked_with_no_verdict_stays_unproven_RED`

#### Scenario: a verdict-proven box is reported awaiting-writer and does not red

- **Given** the same unticked criterion
- **And** a trusted approve verdict comment (`bot_verdict` marker, ACCEPTING verdict, `head` == the
  PR's current head) exists on the PR
- **When** the gate runs with `--pr <n>`
- **Then** it reports `acceptance-proven-awaiting-writer`
- **And** exits zero (green) — no write-back tick required and no push
- **Test:** `tests/test_check_pr_acceptance.py::test_cli_unticked_with_approve_verdict_is_PROVEN_AWAITING_GREEN`

#### Scenario: a changes verdict proves nothing

- **Given** a PR whose only verdict comment is a `changes`/reject marker
- **When** the gate resolves the verdict evidence
- **Then** `verdict_evidence` returns no evidence and the unticked box stays `acceptance-unchecked`
- **And** the gate exits non-zero
- **Test:** `tests/test_check_pr_acceptance.py::test_changes_verdict_does_NOT_prove_unproven_stays_RED`

#### Scenario: a verdict for another head does not prove the current head

- **Given** a verdict marker whose `head` differs from the PR's current head (a stale #852 marker)
- **When** the gate resolves the verdict evidence
- **Then** it returns no evidence and the current-head box stays `acceptance-unchecked`
- **Test:** `tests/test_check_pr_acceptance.py::test_verdict_at_another_head_does_NOT_prove_later_head`
