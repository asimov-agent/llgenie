# Squash-close umbrella guard

## ADDED Requirements

### Requirement: the acceptance gate reads squash-text closes

The merge-time acceptance gate (`scripts/check_pr_acceptance.py`, issue #1792) derives the set of
issues a PR closes from BOTH the live PR body AND the joined squash commit messages, so a close
keyword that lives only in the squash text (the text GitHub's native close-on-merge actually reads)
is held to the linked issue's `## Acceptance criteria`.

#### Scenario: a squash text closes an umbrella with unticked criteria

Given a PR whose squash commit message carries an adjacent `closes #N`
When the acceptance gate runs with that squash text supplied
Then `#N` is in the linked-issue set it checks
And the umbrella's unticked `- [ ]` acceptance criteria make the gate RED
(text: PR #1815, instance #1812).

#### Scenario: a body and a squash close different issues

Given a PR whose body closes `#A` and whose squash text closes `#B`
When the acceptance gate runs with both texts supplied
Then BOTH `#A` and `#B` are in the linked-issue set
And each is checked against its own issue's acceptance criteria.

### Requirement: negation-awareness in the close parse

`closes #N` preceded by an explicit negation (`does not close #N`, `won't close #N`,
`(not closing #N)`, `does NOT close #N`) is NOT treated as a close reference by the
acceptance gate's linked-issue derivation, so a lane can name an umbrella without
triggering the premature-close hold.

#### Scenario: a negated close is not a close

Given a squash text or PR body that says `does not close #N`
When the acceptance gate derives the linked-issue set
Then `#N` is NOT in that set
And the gate does not hold the merge on `#N`.

#### Scenario: an affirmative close still closes

Given a squash text or PR body that says `closes #N` on its own line
When the acceptance gate derives the linked-issue set
Then `#N` IS in that set
And it is checked against the issue's acceptance criteria.

### Requirement: the workflow steps pass the commit range

Both guard workflows (`.github/workflows/ci.yml` and `.github/workflows/scope.yml`) supply the
acceptance-gate step with the pull-request BASE and revision (the squash range), so the squash-text
closes are read live (issue #1589) rather than skipped.

#### Scenario: a PR run supplies the range

Given a `pull_request` run of a guard workflow with a base and head
When the `check-pr-acceptance` step runs
Then it exports `PR_BASE`/`PR_HEAD` for the make target
And the acceptance gate reads the squash closes from that range.
