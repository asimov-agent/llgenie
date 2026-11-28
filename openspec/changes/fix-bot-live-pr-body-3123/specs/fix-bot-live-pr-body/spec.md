## ADDED Requirements

### Requirement: fix-bot checks the live PR body
The fix-bot check loop SHALL fetch the live PR's `body`, `headRefOid` and `baseRefOid` before
`fix-loop-image`, and SHALL pass those values to the check as `PR_BODY`, `PR_HEAD` and `PR_BASE`.

#### Scenario: body-dependent gate runs against the live body
- **Given** a fix-bot run with a linked PR whose body is non-empty
- **When** the check loop starts
- **Then** `PR_BODY` points at a file containing that live body and `PR_HEAD`/`PR_BASE` are the live refs

### Requirement: an empty live body is not a green
A body-dependent check SHALL exit nonzero with an error annotation and no `bot-done ... fixed`
marker when the live body, head or base is empty.

#### Scenario: empty live body
- **Given** the linked PR's body is empty or could not be fetched
- **When** the check loop runs a body-dependent check
- **Then** the step writes `exit=2` and never reaches `fix-loop-image`
