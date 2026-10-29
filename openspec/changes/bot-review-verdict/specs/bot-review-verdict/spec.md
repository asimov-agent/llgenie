# bot-review-verdict — specification

Issue: [#852](https://github.com/asimov-agent/llgenie/issues/852)

## ADDED Requirements

### Requirement: A bot review verdict is a comment marker, never an approval

The pipeline SHALL represent a bot's review decision as a comment marker on the pull request that names
the full 40-hex commit sha it reviewed, because a bot pushes with the owner's PAT and GitHub therefore
refuses its own approval (`reviewDecision` can never leave `REVIEW_REQUIRED`). The marker SHALL be
`<!-- bot-verdict: head=<sha> verdict=<approve|changes> reviewer=<login> -->`, it SHALL NOT be a GitHub
review or a label, and no second identity SHALL be introduced for the review.

WHEN a reviewer posts a verdict,
THEN it writes ONE comment carrying the marker, the verifier's login and the full head sha.

#### Scenario: the producer refuses a sha that is not a head

- **Given** a verdict request whose `--head` is a 7-character sha prefix
- **When** the producer runs
- **Then** it exits non-zero, writes no comment, and says a prefix is not a head

- **Test:** `tests/test_bot_verdict.py::test_post_refuses_a_short_sha`

#### Scenario: the same verdict is posted once

- **Given** a PR whose thread already carries `approve` at head H by reviewer R
- **When** the producer is asked again for `approve` at H by R
- **Then** it posts nothing, and the thread still holds exactly one such comment

- **Test:** `tests/test_bot_verdict.py::test_post_writes_one_comment_and_is_idempotent`

### Requirement: The merge decision accepts a verdict only at the PR's current head

`auto_merge.decide()` SHALL treat a review block (`mergeable: MERGEABLE`, `mergeStateStatus: BLOCKED`,
`reviewDecision: REVIEW_REQUIRED`) as cleared only when the newest trusted verdict's marker names the
PR's CURRENT `headRefOid`. A verdict naming any other sha SHALL NOT clear the block. A verdict of
`changes` at the current head SHALL hold the PR. A verdict SHALL count only when the comment's author is
one of the repository's identities or a bot login AND the `reviewer=` in the marker equals that author.

WHEN the decision reads a review-blocked PR and a verdict for its current head,
THEN it accepts the merge; WHEN the verdict names an older commit, THEN the block stands.

#### Scenario: a stale-sha verdict is refused

- **Given** a review-blocked PR at head H whose thread carries an `approve` marker for an older commit
- **When** the decision and the run read it
- **Then** the reason is the `BLOCKED` merge state and no merge is attempted

- **Test:** `tests/test_auto_merge.py::test_a_stale_verdict_does_not_clear_the_review_block`

#### Scenario: a current-sha verdict is accepted and merged

- **Given** a review-blocked PR at head H whose thread carries an `approve` marker for H from a trusted
  login
- **When** the decision and the run read it
- **Then** the decision accepts it and the run issues ONE admin merge pinned to H

- **Test:** `tests/test_auto_merge.py::test_a_verdict_at_the_current_head_clears_the_review_block_and_merges`

#### Scenario: an untrusted or impersonating marker is not a verdict

- **Given** a marker written by an account that is not a repository identity, or a marker whose
  `reviewer=` names the bot while the comment author is a stranger
- **When** the decision reads it
- **Then** it does not count and the PR stays deferred

- **Test:** `tests/test_auto_merge.py::test_a_verdict_from_an_untrusted_login_does_not_count`,
  `tests/test_auto_merge.py::test_a_stranger_cannot_borrow_a_bot_name_in_the_marker`

#### Scenario: a changes verdict holds a clean PR

- **Given** a CLEAN PR whose thread carries a `changes` verdict at its current head
- **When** the decision and the run read it
- **Then** the reason names the requested changes and nothing is merged

- **Test:** `tests/test_auto_merge.py::test_a_changes_verdict_at_the_head_holds_the_pr`

### Requirement: The verdict reader never costs the gate its automatic trigger

`auto-merge.yml` SHALL keep firing itself: a `workflow_run` on a completed `CI` run, plus the scheduled
sweep. This change reads the verdict inside that gate; it SHALL NOT be the reason the workflow becomes
manual-only.

WHEN the merge workflow's trigger block is read,
THEN an automatic PR-completion trigger is declared and the merge job still demands `success`.

#### Scenario: the automatic trigger guard still passes

- **Given** `.github/workflows/auto-merge.yml` as changed by this change
- **When** the automatic-trigger guard runs
- **Then** it passes, and it fails when `on.workflow_run` is replaced by a manual trigger

- **Test:** `tests/test_bot_pipeline_isolation.py::test_auto_merge_fires_by_itself_when_a_pr_run_completes`
