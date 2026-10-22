# auto-merge-gh-json-fields

## ADDED Requirements

### Requirement: The decision asks `gh` only for fields it has

The merge decision SHALL read its state from exactly one `gh pr view --json` call, and every field name in that
call SHALL be one `gh` accepts. A name `gh` does not have makes it refuse the whole call (`Unknown JSON field`,
exit 1), which kills the run before any decision is reached.

WHEN the decision reads the pull request
THEN the `--json` argument carries only names from `gh`'s own allowlist.

#### Scenario: every requested field exists in gh

Given gh's allowlist, captured from the real CLI
When  the decision's field list is inspected
Then  no requested name falls outside it, and the invented `authorAssociation` is absent.

- **Test:** `tests/test_auto_merge.py::test_the_one_pr_view_call_asks_only_for_fields_gh_has`

#### Scenario: a fake gh refuses an unknown field like the real one

Given the test fake `gh`
When  a `pr view --json` asks for a name that is not in the captured allowlist
Then  it exits non-zero with `Unknown JSON field`, so every end-to-end case in the suite fails on that
regression instead of silently passing.

- **Test:** `tests/test_auto_merge.py::test_the_one_pr_view_call_asks_only_for_fields_gh_has`

### Requirement: A bot author is recognised without an association field

A bot-authored pull request SHALL be recognised from the author login alone (`…[bot]`, `app/…`, or the known
bot logins), because `gh pr view` exposes no author-association field, and a bot PR SHALL be merged only when
the CI run's actor is the owner, a write collaborator, or the bot.

WHEN the opener is a bot account
THEN the bot rule applies, and the viewer is authorised by the run's actor.

#### Scenario: bot logins are bots and humans are not

Given the bot logins GitHub can put on a PR and two human accounts
When  the bot test is applied
Then  every bot login is a bot and no human login is.

- **Test:** `tests/test_auto_merge.py::test_a_bot_login_is_recognised_from_the_login_alone`

#### Scenario: a bot PR merges for the owner's run, a stranger's does not

Given a green, clean PR opened by the bot whose CI run the owner triggered, and one opened by a stranger from
the trusted fork
When  the merge runs
Then  the bot PR merges and the stranger's defers without a merge.

- **Test:** `tests/test_auto_merge.py::test_a_write_collaborator_a_bot_and_the_owner_may_merge_a_stranger_may_not`
