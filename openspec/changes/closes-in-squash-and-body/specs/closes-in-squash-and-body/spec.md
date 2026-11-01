# closes-in-squash-and-body

## ADDED Requirements

### Requirement: a claimed issue is an adjacent close in the squash text and in the PR body

The gate MUST join the non-merge commit messages in the pull request range and treat that text as
the squash body. A claim is an `Issue: #N` line, or a commit subject or pull-request title that ends
with `(#N)`. Each claim MUST be an adjacent `closes|fixes|resolves #N` in the joined text. When a
pull request body is supplied, the adjacent-close set in the body and the adjacent-close set in the
joined text MUST be the same set, and every claim MUST be in it. A range that claims nothing and
closes nothing MUST pass. A `#N` that is only prose MUST NOT be a claim. `closes **#N**` MUST NOT
count as a close.

WHEN the joined commit messages claim an issue and do not adjacently close it
THEN the check fails and names that issue.

#### Scenario: a subject claim without an adjacent close is red

- **Given** a commit whose subject ends with `(#1417)` and whose message has no adjacent close
- **When** the squash check runs with a body that does close `#1417`
- **Then** the check reports that the squash text does not close the claim
- **Test:** `tests/test_check_pr_closing.py::test_a_claim_without_an_adjacent_close_in_the_squash_text_is_red`

#### Scenario: the body and the squash text must close the same issues

- **Given** commit messages that adjacently close `#9` and a body that closes `#10`
- **When** the squash check runs
- **Then** the check reports that the two texts close different issues
- **Test:** `tests/test_check_pr_closing.py::test_the_body_and_the_squash_text_must_close_the_same_issues`

#### Scenario: a chore with no claim passes

- **Given** commit messages and a body that name no issue and close none
- **When** the squash check runs
- **Then** it reports no finding
- **Test:** `tests/test_check_pr_closing.py::test_a_chore_that_claims_nothing_passes`

#### Scenario: a remainder named only in prose is not a claim

- **Given** both texts adjacently close `#9` and the body also mentions `#1413` in prose
- **When** the squash check runs
- **Then** it reports no finding
- **Test:** `tests/test_check_pr_closing.py::test_a_prose_mention_is_not_a_claim`

### Requirement: the unit job shows the body and the base to the gate

`make ci-unit` already runs `make check-pr-closing`. The unit job MUST write the pull request body
to a file and export that path before `make ci-unit`. The guard step and the scope step MUST pass
`PR_BASE`. The make recipe MUST pass `--base`. The branch name MUST be `PR_BRANCH`. The deferred
reason for `check-pr-closing` MUST stay deferred and MUST mention the commit text.

WHEN the unit job workflow is read
THEN its `make ci-unit` step exports the body path and sets `PR_BASE` in `env`, and the `run` block has no GitHub expression.

#### Scenario: the unit job passes the body into ci-unit

- **Given** `.github/workflows/pipeline.yml`
- **When** the unit step is read
- **Then** it exports `PR_BODY` as a file path, sets `PR_BASE`, and the run block contains no expression
- **Test:** `tests/test_check_pr_closing.py::test_the_unit_job_passes_the_body_into_ci_unit`

#### Scenario: the recipe reads the commit range

- **Given** the `check-pr-closing` recipe
- **When** the Makefile is read
- **Then** the recipe passes `--base` and uses `PR_BRANCH` for the branch name
- **Test:** `tests/test_check_pr_closing.py::test_the_make_recipe_passes_the_commit_range`
