## ADDED Requirements

### Requirement: The publish commit text closes its own issue and carries the ticked acceptance mirrors

The architecture bot's publish leg SHALL make the bot commit with a message body built from:
the run marker, a completion line naming the issue, the issue's acceptance criteria in ticked
`- [x]` form, and a `closes #<issue>` line. The commit text SHALL NOT be the issue body.

#### Scenario: the commit text closes the issue the PR closes

- **WHEN** `publish` files a real doc change
- **THEN** the head commit message carries a `closes #<issue>` line
- **AND** the joined commit text closes the same issue the PR body closes

#### Scenario: the commit text carries no unticked box

- **WHEN** the head commit message is read on a published refresh
- **THEN** each acceptance criterion of the issue appears as a `- [x]` line
- **AND** the commit message contains no `- [ ]` line anywhere

### Requirement: The issue's criteria are ticked with a proven naming the publish commit before the PR opens

Once the publish leg has created the commit, it SHALL edit the issue it filed so every
acceptance criterion is `- [x]` and carries a `(proven: ...)` string containing the publish
commit's full sha, and it SHALL make that edit BEFORE creating the pull request.

#### Scenario: the edit precedes the PR open

- **WHEN** `publish` runs on a real drift
- **THEN** the recorded `gh` calls place the issue-body edit before `pr create`
- **AND** the final issue body carries no unticked acceptance item

#### Scenario: the proven names the measured head

- **WHEN** the final issue body is read
- **THEN** every ticked item's proven string names the publish commit's full sha

### Requirement: The PR body carries the acceptance mirror and the hygiene lines

`render_pr` SHALL include a `## Acceptance criteria` section holding the ticked mirror items
(each with its proven string), an `AGENTS: <sha> <bytes>b <lines>l` line naming the main tip
the branch started from, a `BASE: <full-sha> (== origin/main at open)` line, and SHALL end with
the `closes #<issue>` line.

#### Scenario: the PR body shape

- **WHEN** publish opens the PR for a real drift
- **THEN** the PR body contains `## Acceptance criteria` with the ticked mirrors
- **AND** contains an `AGENTS:` line and a `BASE:` line
- **AND** ends with `closes #<issue>`

#### Scenario: dry-run previews the same shape and files nothing

- **WHEN** `publish` runs with `dry=True`
- **THEN** the previewed issue body and PR body show the ticked mirrors and the hygiene lines
- **AND** no issue, branch, commit, push or PR is created

## MODIFIED Requirements

### Requirement: The subprocess policy seam forwards a piped stdin to the child

`scripts/proc.py` is the ONE subprocess policy seam. The capturing policies (`run_ok`,
`run_text`, `run_checked`) SHALL pipe an `input` keyword to the child's stdin instead of
swallowing it with the unknown kwargs: a caller that passes a request body (e.g.
`gh api ... -F body=@-`) means the child to read it. An absent `input` keeps the previous
inherited-stdin behavior.

#### Scenario: a caller's request body reaches the child

- **WHEN** `run_ok` (or `run_text` / `run_checked`) is called with `input="text"`
- **THEN** the child reads exactly that text on stdin
- **AND** a call without `input` behaves exactly as before
