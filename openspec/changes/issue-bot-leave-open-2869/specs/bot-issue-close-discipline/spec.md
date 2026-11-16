## ADDED Requirements

### Requirement: A close verdict that cites an open implementing PR holds the issue open

The issue-bot verdict vocabulary SHALL carry a fourth verdict, `hold`, and the `apply-verdict` step
SHALL convert a `close` verdict into a hold when the verdict's evidence or reason cites a number
that resolves to an OPEN pull request whose title or body names the issue (a closing keyword
adjacent to `#<issue>`, a `(#<issue>)` title reference, or an `Issue: #<issue>` line). A hold SHALL
leave the issue OPEN, post a comment naming the open PR and the reason the issue is left open, post
the `bot-done` claim-release marker, and remove the queue labels — and it SHALL NOT close the issue,
add `agent:closed`, or print the close comment.

#### Scenario: Close verdict citing an open implementing PR

- **WHEN** `apply-verdict` parses a `TRIAGE: close` whose `EVIDENCE:` cites `#<n>` and `#<n>` is an
  OPEN pull request whose body carries a closing reference to this issue
- **THEN** the issue is not closed, no `agent:closed` label is added, a hold comment names `#<n>`,
  and the lane's claim is released with the `bot-done` marker

#### Scenario: Hold verdict stated directly

- **WHEN** `apply-verdict` parses a `TRIAGE: hold` whose `EVIDENCE:` names the open PR
- **THEN** the same hold actions run and the step exits 0

#### Scenario: Duplicate close still closes

- **WHEN** `apply-verdict` parses a `TRIAGE: close` whose evidence cites only closed or non-PR
  numbers
- **THEN** the issue closes with `--reason "not planned"` and the `agent:closed` label as before

### Requirement: The decision block and playbooks state the close reasons and the leave-open rule

`DECISION_BLOCK` in `scripts/issue_implementer.py` SHALL print the `TRIAGE: hold` shape alongside
`implement`, `refine` and `close`. The lane playbook `.hermes/skills/issue-triage/SKILL.md`, the
planner playbook `agents/llgenie-planner/skills/github-issue-triage/SKILL.md` and the implementer
reference `agents/llgenie-issse-implementer/skills/software-development/llgenie-issue-to-pr/references/planner-stale-state.md`
SHALL each state the two close reasons (`not_planned` for duplicate/invalid work; `completed` when a
merged PR's closing reference closes the issue at merge) and the rule that an issue already
implemented by an OPEN PR stays open with the lane's claim abandoned and a hold comment naming the
PR.

#### Scenario: Playbook text is held to the rule

- **WHEN** `make test-unit` runs the coverage for this change
- **THEN** a test asserts each of the three playbook files carries the leave-open rule and the
  close-reason split, failing when the text drifts

### Requirement: The bot close-reason read names bot-closed issues merged PRs implement

`make bot-close-reasons-report` (backed by `scripts/bot_close_reasons.py`) SHALL read closed issues
that a merged pull request's closing reference targets and that the bot closed — identified by the
`agent:closed` label or a Bot closer — and print for each: the issue number, its current
`state_reason`, and the merged PR that closes it. An issue whose `state_reason` is `not_planned`
while a merged PR implements it SHALL be flagged as contradicting its own close evidence. The read
SHALL exit non-zero when it cannot read the data, and it SHALL print counts, never secret values.

#### Scenario: A corrected closure appears with its corrected reason

- **WHEN** the read runs against the live repo and an issue like #2048 was bot-closed with
  `not_planned`, its reason later corrected to `completed`, and a merged PR carries its closing
  reference
- **THEN** the row names the issue with reason `completed` and the merged PR

#### Scenario: An uncorrected closure is flagged

- **WHEN** a bot-closed issue still carries `not_planned` while a merged PR's closing reference
  targets it
- **THEN** the row is flagged as contradicting its close evidence
