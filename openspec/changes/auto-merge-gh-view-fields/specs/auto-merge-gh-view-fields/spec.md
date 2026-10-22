# auto-merge-gh-view-fields

## ADDED Requirements

### Requirement: The merge decision requests only fields `gh pr view` has

`scripts/auto_merge.py` SHALL build every `gh pr view --json` request from one constant, and every field
name in that constant SHALL exist in `gh pr view --json`'s own allowlist. `authorAssociation` SHALL NOT be
requested or read. The allowlist SHALL be captured in `tests/fixtures/gh-pr-view-fields.json` from the real
CLI's `gh pr view --json __probe__` answer, and a unit test SHALL compare the constant against it.

WHEN a field name is added to the constant that `gh` does not have
THEN `make test-unit` fails naming the field, rather than the merge workflow dying at run time.

#### Scenario: every requested field is in gh's captured allowlist

Given the allowlist captured from `gh pr view --json __probe__`
When  the module's requested field names are read
Then  each one exists in the allowlist, and `authorAssociation` is in neither.

- **Test:** `tests/test_auto_merge.py::test_every_requested_field_is_in_ghs_own_allowlist`

#### Scenario: the state call asks for exactly the constant

Given a fake `gh` that records its argv
When  `pr_state` reads a PR
Then  the `--json` argument is the `PR_VIEW_STATE_FIELDS` joined by commas, and carries no invented name.

- **Test:** `tests/test_auto_merge.py::test_pr_state_requests_exactly_the_locked_field_list`

#### Scenario: explain runs end to end on a real PR

Given an authenticated `gh` and a real PR in the repository
When  `make auto-merge-explain PR=511 REPO=asimov-agent/llgenie` runs
Then  it prints the state and a verdict, and exits 0 without writing.

- **Test:** live — `make auto-merge-explain PR=511 REPO=asimov-agent/llgenie` (real `gh`; not hermetic)

### Requirement: A bot author is recognised by its login alone

The author gate SHALL treat a PR whose `author.login` is a GitHub App login (`app/github-actions`) or ends
in `[bot]` as bot-authored, and SHALL then allow the merge only when the CI run's actor is the owner, a
write collaborator, or a bot. It SHALL NOT read `authorAssociation`.

WHEN a bot-authored PR is evaluated
THEN the decision is built from `author.login` and the run's actor, and an empty actor is a named deferral.

#### Scenario: an App bot and a `[bot]` login are recognised without an actor

Given a PR opened by `app/github-actions`, and one opened by `dependabot[bot]`
When  the author gate runs with no actor
Then  both defer, naming the bot and the empty ACTOR.

- **Test:** `tests/test_auto_merge.py::test_a_bot_author_is_recognised_by_its_login_alone`

#### Scenario: a bot PR merges when the actor is the owner

Given a bot-opened, green, CLEAN PR
When  the job runs with ACTOR set to the repository owner
Then  it squash-merges the PR.

- **Test:** `tests/test_auto_merge.py::test_a_bot_author_is_recognised_by_its_login_alone`

#### Scenario: the human and stranger rules are unchanged

Given a PR opened by a collaborator with write, and one opened by a stranger
When  the job runs
Then  the collaborator's PR merges and the stranger's defers without a merge.

- **Test:** `tests/test_auto_merge.py::test_a_write_collaborator_a_bot_and_the_owner_may_merge_a_stranger_may_not`
