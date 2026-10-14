# issue-bot-triage

## ADDED Requirements

### Requirement: The bot reads the issue body and every comment

`dispatch` SHALL fetch the issue with `gh issue view <n> --comments` and the agent's input SHALL
contain the title, state, author, the body, and every comment in chronological order with its
author and date, followed by the decision instruction and the exact verdict format.

#### Scenario: the thread reaches the agent

- **GIVEN** an issue with two comments
- **WHEN** `dispatch` writes `issue.md`
- **THEN** the file SHALL contain both comments with their authors and dates
- **AND** it SHALL state the three verdicts and their required blocks

### Requirement: The verdict is one of three, and closing needs evidence

`apply-verdict` SHALL act on `TRIAGE: implement|refine|close`. `implement` SHALL mutate nothing;
`refine` SHALL post one comment containing the `REFINED:` restatement and add `agent:refined`,
opening no PR; `close` SHALL post the reason with its `EVIDENCE:` block, close the issue, and add
`agent:closed` while removing `agent:implement`. A `close` with no `EVIDENCE:` block, a `refine`
with no `REFINED:` block, and an unrecognised or missing verdict SHALL each exit non-zero having
mutated nothing.

#### Scenario: a refine is a comment, not a PR

- **WHEN** the verdict is `refine` with a `REFINED:` block
- **THEN** exactly one comment SHALL be posted and `agent:refined` added
- **AND** no PR SHALL be created

#### Scenario: no evidence, no close

- **WHEN** the verdict is `close` without an `EVIDENCE:` block
- **THEN** the command SHALL exit non-zero and change nothing

### Requirement: A decided issue is not picked again

`dispatch` SHALL skip any issue carrying `agent:refined` or `agent:closed`, so a refine or close
cannot repeat every run, and neither verdict SHALL consume the daily PR cap.

#### Scenario: decided issues are skipped

- **GIVEN** three labelled issues, two of them already labelled `agent:refined`/`agent:closed`
- **WHEN** `dispatch` picks one
- **THEN** it SHALL pick the undecided one
