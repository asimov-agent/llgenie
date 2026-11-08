# Reactor dispatch refusal

## ADDED Requirements

### Requirement: A refused dispatch is surfaced on the PR and does not red the reactor job

`scripts/run_failure_reactor.py` dispatches `fix-bot` for a red same-repo PR (route A). When
`gh workflow run` exits non-zero the reactor MUST treat it as a refused dispatch, not a crash: it
MUST parse the HTTP status and the scope the credential lacks, post
`repair unavailable: <status> — missing scope: <scope>` on the PR, release the claim it wrote before
the dispatch (`bot-done`), emit a `::warning::` annotation, and exit 0. A refusal is never swallowed
and never reds the whole `react` job: the reactor's own reds keep meaning "the reactor broke".

#### Scenario: a 403 refusal is posted on the PR and the job stays green

Given a red same-repo PR whose route A dispatch is refused with
`HTTP 403: Resource not accessible by personal access token (…/dispatches)`,
When the reactor routes the run,
Then it exits 0, posts one `pr comment` carrying `repair unavailable`, `HTTP 403` and the missing
scope (`workflow` / `Actions: write`), marks that comment `bot-done` so the claim is released, emits
a `::warning::` annotation, and files no issue.

- **Test:** `tests/test_run_failure_reactor.py::test_a_refused_dispatch_is_posted_on_the_pr_and_does_not_red_the_job`

#### Scenario: an unrecognisable refusal is still surfaced

Given a dispatch that fails with stderr carrying no `HTTP <code>` shape,
When the reactor routes the run,
Then it still posts `repair unavailable` on the PR with `HTTP ?` and the raw detail, and exits 0.

- **Test:** `tests/test_run_failure_reactor.py::test_a_refusal_with_no_recognisable_status_is_still_surfaced`

### Requirement: The status maps to the scope the credential lacks

The refusal MUST name what a maintainer has to grant, per HTTP status: `workflow` (classic PAT) or
`Actions: write` (fine-grained PAT) for 403, an invalid-or-expired credential for 401, a workflow not
visible to the credential for 404, and `unknown` for any other answer. An unrecognised refusal is a
refusal with no status, never a silent pass.

#### Scenario: each status names its own missing scope

Given `gh` stderr for a 403, a 401 and a 404,
When `parse_dispatch_refusal()` reads them,
Then the 403 names `workflow`/`Actions: write`, the 401 names an invalid or expired credential, the
404 names a workflow not visible to the credential, and an unrecognised message yields no status with
an `unknown` scope.

- **Test:** `tests/test_run_failure_reactor.py::test_a_refusal_names_the_status_and_the_scope_the_credential_lacks`

### Requirement: A successful dispatch is unchanged

A dispatch the API accepts MUST behave exactly as before: the PR is claimed, `fix-bot.yml` is
dispatched with the owner identity, the reactor prints the dispatch, and it files no issue. A missing
`DISPATCH_TOKEN` remains a loud failure (exit 1) with no dispatch and no issue.

#### Scenario: an accepted dispatch still claims and dispatches as the owner

Given a red same-repo PR and a dispatch credential the API accepts,
When the reactor routes the run,
Then the claim precedes one `workflow run fix-bot.yml` call carrying the owner token, and no issue is
filed.

- **Test:** `tests/test_run_failure_reactor.py::test_a_red_same_repo_pr_run_dispatches_the_fix_bot`

#### Scenario: a missing dispatch credential stays loud

Given no `DISPATCH_TOKEN` in the environment,
When the reactor routes a red PR run,
Then it exits 1 naming the variable, dispatches nothing and files nothing.

- **Test:** `tests/test_run_failure_reactor.py::test_a_missing_dispatch_token_is_loud_and_dispatches_nothing`
