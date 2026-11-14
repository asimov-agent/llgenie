## ADDED Requirements

### Requirement: The architecture bot stamps its PR body through the one stamp authority

`scripts/architecture_bot.py` SHALL build its PR body pair exclusively through
`bot_preflight.stamp_body` stamped with a record from `bot_preflight.resolve_record`, and SHALL NOT
compose an `AGENTS:`/`BASE:` pair with a local restatement. `publish` SHALL resolve the record before
it creates an issue, a branch, or a commit; when no `main` ref resolves it SHALL refuse, naming the
refs it tried. Both the opened PR body and the `--dry` preview body SHALL carry the measured pair.

#### Scenario: the opened body passes the gate it will be judged by

- **WHEN** `publish` composes the PR body for a branch cut from a resolvable `main`
- **THEN** `check_pr_hygiene.pr_agents_line_findings` on that body returns `[]`
- **AND** the same body with the pair removed returns `agents-line`

#### Scenario: an unmeasurable base refuses early

- **WHEN** `publish` runs in a checkout where neither `origin/main` nor any allowed fallback ref resolves
- **THEN** it raises naming the refs tried, and no issue, branch, commit, or GitHub write has happened

#### Scenario: the dry preview carries the pair

- **WHEN** `publish --dry` prints the body it would open with
- **THEN** the printed body contains the flush-left `AGENTS:`/`BASE:` pair from the measured record

### Requirement: The stamp-producer roster is derived from the tree

`tests/test_bot_stamp_body.py` SHALL derive its producer roster by scanning the tree, not a hardcoded
list: every `scripts/*.py` containing a real `gh pr create` call MUST contain the
`bot_preflight.stamp_body` call, and every `.github/workflows/*.yml` whose non-comment steps run
`gh pr create` MUST run `make bot-stamp-body` before the first create and pass the body via
`--body-file`.

#### Scenario: a new unstamped producer reds the suite

- **WHEN** a scratch tree holds a `scripts/` module that runs `gh pr create` without stamping
- **THEN** the derived roster names that module as unstamped
