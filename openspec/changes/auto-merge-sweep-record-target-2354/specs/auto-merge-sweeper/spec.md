# Spec delta: auto-merge-sweeper

## ADDED Requirements

### Requirement: The sweepers record on one durable open tracker

The 30m auto-merge sweeper's record step (step 5) and the auto-rebase-resolve sweeper's record step
(step 6) SHALL each name exactly one record target — the rolling record tracker issue #2652, which
is never closed by implementation PRs — and SHALL record once per run with a fixed greppable first
line (`[sweep <UTC-stamp>] merged=<n> approved=<n> deferred=<n>` /
`[rebase-sweep <UTC-stamp>] dispatched=<n> rebased=<n> deferred=<n>`) followed by one line per
deferred/dispatched PR with its reason. The steps SHALL NOT reference the kanban tick card id
`cc5d2bd4083a` or closed issues #2101/#2158 as record targets.

#### Scenario: record lands on the tracker

- WHEN a sweep run completes against asimov-agent/llgenie
- THEN exactly one comment is posted to issue #2652 whose first line matches
  `^\[sweep .*\] merged=[0-9]+ approved=[0-9]+ deferred=[0-9]+`
- AND each deferred PR appears with a one-line reason.

#### Scenario: live procedure carries no dead-card reference

- WHEN `git grep -n 'cc5d2bd4083a' origin/main -- agents/ scripts/ .github/ docs/` is replayed after
  this change merges
- THEN it exits non-zero (no hits in live procedure dirs); dated CHANGES.md/agent-wiki records that
  name the orchestrator-tick CRON JOB id stay as historical records.

### Requirement: Live sweeper prompt equals the versioned copy

The live planner cron job `db0a3e1a3d7c` prompt SHALL be byte-identical (modulo the single trailing
newline framing) to `agents/llgenie-planner/prompts/llgenie-auto-approve-merge.md`, proven by
`make check-cron-drift` on the host.

#### Scenario: drift gate green on the host

- WHEN `make check-cron-drift` runs on the configured host after this change
- THEN it prints `OK db0a3e1a3d7c` and `OK 71c5192ebdba` and exits 0.
