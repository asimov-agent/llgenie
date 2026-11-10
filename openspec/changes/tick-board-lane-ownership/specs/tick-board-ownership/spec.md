## ADDED Requirements

### Requirement: the tick prints a measured board-ownership invariant with no write path

The orchestrator tick SHALL print, every pass, one `board-ownership:` line measured from
`kanban list --json` (`assignee`, `status`), naming `planner_owned_ready` against its expected
ceiling and `lanes_with_ready`, and it SHALL report `ok` or a violation count. The tick SHALL NOT
create, edit, or reassign any card while measuring.

#### Scenario: a healthy board reads ok inside the planner domain
- **Given** a board where planner-owned ready cards sit at or below the ceiling and lane-created ready cards are legitimately held
- **When** the tick's ownership section runs
- **Then** the line reads `planner_owned_ready=<n> (expect <= <ceiling>) lanes_with_ready=<m> -> ok`
- **And** auto-decomposer-created cards are counted as legitimate, not as violations

#### Scenario: a bulk rewrite of lane-created ready cards to the planner goes red
- **Given** a board where ready cards created by a lane were rewritten to `llgenie-planner`
- **When** the same section runs
- **Then** the line reports the violation count instead of `ok`

#### Scenario: an empty board still prints the line
- **Given** a board with no cards
- **When** the tick runs the ownership section
- **Then** the `board-ownership:` line is still printed (zero counts), never skipped

### Requirement: the tick counts mis-profiled runs

For every task in status `running`, the tick SHALL compare the profile recorded in `task_runs`
(section D of `kanban list --json`) with the task's `assignee` and print the count of mismatches
every pass.

#### Scenario: a running task whose run profile is not its card's assignee is counted
- **Given** a board whose running tasks include mis-profiled runs (e.g. six running tasks whose `task_runs.profile` differs from the card `assignee`)
- **When** the tick's mis-profiled-run section runs
- **Then** the printed counter reports exactly the number of mismatches (six)

#### Scenario: a healthy running board reports zero
- **Given** running tasks all executed under their own lane profile
- **When** the same section runs
- **Then** the counter reads zero

### Requirement: a single-card edit leaves every other assignee byte-identical

A single-card `kanban edit`/`reassign` SHALL leave the `assignee` field of every OTHER card
byte-identical to its pre-edit value, and the ownership invariant check SHALL stay at zero
violations after such an edit.

#### Scenario: reassigning one card does not touch the rest
- **Given** a board of several cards owned by different lanes
- **When** one card is reassigned
- **Then** every other card's `assignee` is byte-identical to before the edit
- **And** the ownership invariant reports zero violations
