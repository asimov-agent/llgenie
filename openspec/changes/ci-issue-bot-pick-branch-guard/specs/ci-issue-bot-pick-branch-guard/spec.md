# ci-issue-bot-pick-branch-guard

## ADDED Requirements

### Requirement: the pick refuses issues whose lane branch already exists

`scripts/issue_implementer.py`'s pick must treat a remote branch carrying the prefix
`agent/issue-<n>` (exact, or `agent/issue-<n>-…`) for a candidate issue the same way it treats
a live claim: the issue is skipped, the skip is named in the log with the branch it skips on,
and the pick continues to the next candidate. A missing branch must never abort the pick — a
refs-probe failure or 404 answers "no branch".

#### Scenario: a foreign lane branch skips its issue

Given open `agent:implement` candidates #7 (oldest, with remote branch
`agent/issue-7-ci-security-p0`) and #11, when `_pick_free` runs; then it returns issue #11 and
the run's output names `branch-exists` with `agent/issue-7-ci-security-p0`.

#### Scenario: no branch answers the pick unchanged

Given the same candidates and a refs probe that fails for both (no such refs); when
`_pick_free` runs; then it returns #7 and nothing raises.

### Requirement: an exhausted pick says why it was the branches

When every remaining candidate was skipped because its lane branch exists, `dispatch` must
return action `none` with reason `branch-exists` naming the skipped issues, and the CLI must
print `action=none` and `reason=branch-exists` so the issue-bot workflow maps it to
`dispatch=false` without running the implement legs.

#### Scenario: every candidate is branch-covered

Given candidates #7 and #11 both carrying `agent/issue-<n>-…` remote branches; when `dispatch`
runs; then it returns `action=none`, `reason=branch-exists`, and lists #7 and #11 as skipped.

### Requirement: a pinned dispatch onto a branched issue is refused

A forced dispatch (`FORCE_ISSUE`, the label-event or manual pin) onto an open issue that already
carries an `agent/issue-<n>…` remote branch must refuse with `action=none` and reason
`branch-exists` BEFORE writing the claim comment or `issue.md` — the branch's owner works that
issue, and the bot spends no implement leg on it.

#### Scenario: a label event pins #7 which has a lane branch

Given a label event forcing issue #7 while `agent/issue-7-ci-security-p0` exists on the remote;
when `dispatch` runs; then it returns `action=none` with `reason=branch-exists`, writes no
claim comment, and issues no `issue.md` pick line naming a branch.
