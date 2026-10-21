# auto-merge-green-prs

## ADDED Requirements

### Requirement: A green, conflict-free PR is merged by CI

The pipeline SHALL squash-merge a pull request without waiting for a human, but ONLY when every
PR-relevant job of the run is green **and** the PR is conflict-free and mergeable
(`mergeStateStatus == CLEAN`, `mergeable == MERGEABLE`). A PR that is red, conflicted, behind `main`,
blocked, a draft, from a fork, or carrying `do-not-merge` SHALL NOT be merged.

WHEN a `pull_request` run's jobs all finish successfully
THEN the `auto-merge` job SHALL merge the exact head commit the run validated, and SHALL defer to a human
(exit 0, reason printed) in every other case.

#### Scenario: a green, clean PR is merged

Given a same-repo, non-draft PR whose pipeline is green and whose `mergeStateStatus` is `CLEAN`
When  the `auto-merge` job runs
Then  it squash-merges the run's head SHA with `--match-head-commit`, deletes the branch, and verifies what
      the merge closed.

- **Test:** `tests/test_auto_merge.py::test_the_merge_is_squash_head_pinned_and_branch_deleted`

#### Scenario: a conflicted or behind PR is left for a human

Given a PR whose `mergeStateStatus` is `DIRTY` (conflicts) or `BEHIND` (needs an update)
When  the `auto-merge` job runs
Then  it prints the state, merges nothing, and exits 0 — a deferral is not a failed run.

- **Test:** `tests/test_auto_merge.py::test_only_a_clean_merge_state_is_merged`

#### Scenario: the job waits for every PR-relevant job, and each must have SUCCEEDED

Given `ci.yml`'s job graph
When  the `auto-merge` job is read
Then  it `needs:` guard, ci-images, linux, macos, engine-base, engine-matrix, engine-image and
      linux-published, it requires `needs.<job>.result == 'success'` for every one of them — a SKIPPED
      job is not a passed job — and the push-only `engine-published-test` is deliberately not in `needs:`.

- **Test:** `tests/test_auto_merge.py::test_the_job_needs_every_pr_relevant_job`

#### Scenario: fork, draft and main are never merged

Given a draft PR, a PR whose head is in another repository, or a PR whose head branch is `main`
When  the job's condition is read
Then  it excludes all three.

- **Test:** `tests/test_auto_merge.py::test_fork_draft_and_main_are_excluded`

#### Scenario: do-not-merge holds a PR

Given a green, clean PR carrying the `do-not-merge` label
When  the `auto-merge` job runs
Then  it prints the hold, merges nothing, and exits 0.

- **Test:** `tests/test_auto_merge.py::test_do_not_merge_holds_the_pr`

#### Scenario: the merge uses the PAT, not the job token

Given a merge made with `GITHUB_TOKEN` starts no workflows
When  the merge step's env is read
Then  it uses `secrets.BUMP_TOKEN` and never `github.token`, so the post-merge run on `main` happens.

- **Test:** `tests/test_auto_merge.py::test_the_merge_uses_the_owner_pat`

### Requirement: The merge proves what it closed

After the merge, `make verify-closure PR=<n>` SHALL read the merged PR's `closingIssuesReferences` and
fail, naming the issue, when a claimed closing reference is still open.

WHEN a PR that claimed `closes #n` is merged
THEN the verification SHALL pass only if `#n` is closed; an unbound keyword SHALL red the run.

#### Scenario: a bound closing keyword passes

Given a merged PR whose `closingIssuesReferences` names a closed issue
When  `make verify-closure` runs
Then  it prints the closed issue and exits 0.

- **Test:** `tests/test_auto_merge.py::test_verify_closure_passes_for_a_closed_reference`

#### Scenario: an unbound keyword fails loudly

Given a merged PR whose closing reference is still `OPEN`
When  `make verify-closure` runs
Then  it exits non-zero naming that issue.

- **Test:** `tests/test_auto_merge.py::test_verify_closure_fails_for_an_open_reference`

### Requirement: The policy is stated once

`AGENTS.md` SHALL state the new merge policy — CI merges a green, conflict-free, same-repo, non-draft PR;
the agent never runs `gh pr merge` itself; `do-not-merge` holds a PR — and SHALL NOT still carry the old
unconditional "the agent never merges, even when asked" wording as the operative rule.

WHEN `AGENTS.md` is read
THEN the merge rule names the CI job and the hold, and the older "an APPROVED PR is merged" paragraph does
not contradict it.

#### Scenario: AGENTS.md states the policy

Given `AGENTS.md`
When  its Git workflow section is read
Then  it names the `auto-merge` job, the conditions, the `do-not-merge` hold, and that the agent still
      never merges by hand.

- **Test:** `tests/test_auto_merge.py::test_agents_md_states_the_new_policy`
