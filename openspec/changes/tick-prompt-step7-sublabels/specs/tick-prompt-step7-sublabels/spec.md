## ADDED Requirements

### Requirement: STEP 7 sub-item labels are unique and consecutive

The versioned planner tick procedure SHALL number STEP 7's sub-items `7a`, `7b`, `7c` consecutively, and no `6a`/`6b`/`6c`/`6d` label SHALL appear under STEP 7. STEP 6 SHALL keep its `6a`–`6d` numbering unchanged. Every in-file cross-reference to a STEP 7 sub-item SHALL cite its `7x` label.

#### Scenario: STEP 7 labels at the merged head

- **WHEN** the STEP 7 block in `agents/llgenie-planner/prompts/llgenie-orchestrator-tick.md` is read at the merged head
- **THEN** the sub-items read `7a.`, `7b.`, `7c.` and no line under STEP 7 carries `6a.`/`6b.`/`6c.`/`6d.`

#### Scenario: STEP 6 is untouched

- **WHEN** the same file is read at STEP 6
- **THEN** the sub-items still read `6a.`, `6b.`, `6c.`, `6d.` unchanged

#### Scenario: The report template cites the collapse rule unambiguously

- **WHEN** the report template line is read at the merged head
- **THEN** it cites `(step 7b)` beside the duplicate-collapse rule, and no `(step 6b)` citation remains in the file

#### Scenario: Tree and live planner profiles agree

- **WHEN** `make sync-agent-profile PROFILE=llgenie-planner CHECK=1` runs at the merged head
- **THEN** it reports the tick prompt (and the two formerly live-edited planner prompts) byte-identical tree↔live
