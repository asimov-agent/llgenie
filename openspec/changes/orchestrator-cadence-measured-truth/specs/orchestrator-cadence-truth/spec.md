## ADDED Requirements

### Requirement: the planner's own text states the configured cadence and the measured delivered cadence as separate numbers

Every planner-owned document that states the `llgenie-orchestrator-tick` cadence SHALL name the
configured interval (30m) and the measured delivered start-to-start cadence (median 40.0 min, cause:
Hermes re-arms `next_run` from completion, so delivered cycle = interval + run duration) as distinct
numbers, and SHALL NOT assert any other cadence as fact.

#### Scenario: SOUL.md quotes the measured truth
- **Given** `agents/llgenie-planner/SOUL.md` describing the recurring tick
- **When** the document is read after this change
- **Then** it says the tick is configured `every 30m` and delivers a measured start-to-start median of 40.0 min, naming the completion-based re-arm as the cause
- **And** no sentence claims 45 minutes

#### Scenario: the tick contract separates configured from delivered
- **Given** `orchestrator-tick-contract.md` Schedule and pitfalls lines
- **When** the document is read after this change
- **Then** Schedule keeps 30m as the CONFIGURED value and names 40.0 min as the DELIVERED median, so neither number is quoted as the other

#### Scenario: the pass-shape reference no longer hedges a range
- **Given** `when-to-use-and-pass-shape.md`
- **When** the document is read after this change
- **Then** it states configured `every 30m` with the measured delivered median, not "every 30–45 min"

### Requirement: The tick preflight is an explicit measured step ahead of precedence
The orchestrator tick prompt SHALL run the explicit `git fetch origin main` and
`rev-list --left-right --count HEAD...origin/main` as its first step, ahead of any
precedence step, and the contract SHALL list that fetch as step 0 of the ordered pass. A
dirty primary checkout SHALL be reported with its blocking paths at the fetched
`origin/main` sha and never cleaned by the planner.

#### Scenario: the fetch precedes the precedence step
- **Given** the tick prompt `agents/llgenie-planner/prompts/llgenie-orchestrator-tick.md`
- **When** the prompt is read after this change
- **Then** STEP 1 names `git -C "$REPO" fetch origin main` and `rev-list --left-right --count HEAD...origin/main` explicitly, ahead of the precedence step (STEP 4 onward)

#### Scenario: the contract carries preflight as step 0
- **Given** `references/orchestrator-tick-contract.md`'s ordered-pass table
- **When** the table is read after this change
- **Then** step 0 is the explicit preflight fetch, ordered before the precedence step

#### Scenario: dirty checkout is reported, not cleaned
- **Given** the tick prompt's board-measurement step
- **When** the primary checkout is dirty at the fetched `origin/main`
- **Then** the prompt requires quoting `git status --porcelain` blocking paths and forbids the planner from resetting, stashing, or cleaning that checkout
