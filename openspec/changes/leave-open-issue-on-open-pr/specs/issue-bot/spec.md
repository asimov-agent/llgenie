# leave-open-issue-on-open-pr

## ADDED Requirements

### Requirement: an OPEN implementing PR holds the issue open; it is never closed

An issue that an OPEN PR implements and is awaiting merge is `hold`, never `close`. The lane
abandons its own claim and posts ONE hold comment naming the PR; the issue stays OPEN, carries
no `agent:closed` label, and its closing keyword on that PR closes it as `completed` on merge.

WHEN `apply_verdict` receives a `TRIAGE: hold` verdict with a `PR: #<n>` block for an issue an
open implementing PR already covers,

THEN the issue is NOT closed,

AND it is NOT labelled `agent:closed`,

AND exactly one comment is posted, naming that PR,

AND the comment carries a `bot-done: <implementer> … held` marker releasing the lane's own claim,

AND no PR is opened.

WHEN the verdict is `hold` but carries no `PR:` block,

THEN `apply_verdict` refuses loudly and mutates nothing.

#### Scenario: a `hold` verdict leaves the issue open for the open implementing PR

- **Given** an issue already implemented by an open PR (#2863) that is awaiting merge
- **When** the triage emits `TRIAGE: hold\nPR: #2863\nEVIDENCE: …`
- **Then** `apply-verdict` posts exactly one hold comment naming `#2863`, releases the
  implementer's own claim (`bot-done: … held`), does not call `issue close`, does not add
  `agent:closed`, and opens no PR
- **Test:** `tests/test_issue_implementer.py::test_a_hold_leaves_the_issue_open_and_posts_a_hold_comment_naming_the_pr`

#### Scenario: a `hold` without a PR is refused

- **Given** a `TRIAGE: hold` verdict with evidence but no `PR:` block
- **When** `apply-verdict` runs
- **Then** it exits non-zero and posts no comment, closes no issue, and labels nothing
- **Test:** `tests/test_issue_implementer.py::test_a_hold_without_a_pr_block_is_refused_and_mutates_nothing`

### Requirement: the triage playbook names two close reasons and the leave-open rule

The lane skill(s) and the machine-read decision block distinguish the two reasons a close is a
close (`not_planned`: duplicate / invalid / discontinued; `completed`: a MERGED PR did it) from
the one case that must never close: `hold` for an OPEN implementing PR awaiting merge.

WHEN a triage agent reads an issue that an OPEN implementing PR already covers,

THEN the playbook it is preloaded with tells it to emit `hold` (naming the PR) instead of a
`close`, and reserve `close` for a duplicate, an invalid/discontinued issue (`not_planned`) or
an issue a MERGED PR implemented (`completed`).

#### Scenario: the implementer's triage skill teaches hold

- **Given** the `.hermes/skills/issue-triage/SKILL.md` Preamble loaded for an issue-bot triage
- **When** the issue it reviews is already implemented by an open PR awaiting merge
- **Then** the skill text names the `hold` verdict shape and states the open-PR case is never a
  close
- **Test:** `tests/test_agent_skills.py::test_this_tree_passes_the_gate` (structural) plus
  `make check-agent-skills`; the verdict shape itself is locked by
  `tests/test_issue_implementer.py::test_parse_verdict_reads_a_hold_pr_block` and the
  `apply-verdict` hold tests

### Requirement: a backfill read names bot-closed not_planned issues a merged PR closes

A read-only report names every issue the issue-bot closed as `state_reason=not_planned` that a
MERGED PR carries a `closes #` reference to, so its reason can be corrected to `completed`. The
read runs on GitHub through `gh` and never writes.

WHEN `make issue-close-backfill` runs against a repository whose merged PRs close a bot-closed
issue that still carries `state_reason=not_planned`,

THEN the report names that issue, the merged PR that closes it, and flags it `NEEDS-CORRECTION`,

AND an issue already carrying `completed` is named as corrected (not flagged).

#### Scenario: the backfill names a bot-closed not_planned issue a merged PR closes

- **Given** a merged PR whose `closingIssuesReferences` contain a bot-closed issue closed as
  `not_planned`
- **When** `issue_close_backfill.read` runs on the repository
- **Then** it reports that issue with `needs_correction == True`, naming the merged PR
- **Test:** `tests/test_issue_close_backfill.py::test_backfill_names_a_bot_closed_not_planned_issue_a_merged_pr_closes`

#### Scenario: an already-corrected issue is reported as corrected, not flagged

- **Given** #2048, bot-closed but hand-corrected to `state_reason=completed`, closed by merged
  PR #2863
- **When** `issue_close_backfill.read` runs
- **Then** #2048 appears in the read with its corrected `completed` reason and
  `needs_correction == False`
- **Test:** `tests/test_issue_close_backfill.py::test_backfill_labels_an_already_corrected_issue_completed`
