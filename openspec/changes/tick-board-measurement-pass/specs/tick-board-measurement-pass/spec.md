# Make the orchestrator tick a procedure: one measurement command, ordered steps

## ADDED Requirements

### Requirement: the tick runs one measurement command that prints fixed sections A–G in order

The orchestrator tick must obtain every deterministic board measurement from a
single versioned command `tick_board.sh` that prints sections under the fixed
headers `A. PREFLIGHT`, `B. OPEN PRs`, `C. LANES`, `D. QUEUE`, `E. STALLED
WORKERS`, `F. CI AT THE TIP`, and `G. LANE DRIFT` in that fixed order. A step
either has a section of that output to act on, or it did not run.

#### Scenario: the measurement command lists the seven sections in order

Given `tick_board.sh` run against a repository (the fixture-based tests),
when the human or a step reads its output,
then the section headers appear in the exact order A, B, C, D, E, F, G.

#### Scenario: the prompts every step to name its command and evidence

Given a pass over the board,
when the tick runs,
then every numbered step names the exact command it runs and the output line it
must quote as evidence, and a step with no quoted line is reported as not run.

### Requirement: red PRs and the board-wide stale-base sweep precede backlog dispatch

The tick must apply the red-PR priority before any new-backlog dispatch: every
open PR whose base differs from the freshly-fetched `origin/main` is STALE and is
handled as ONE board-wide sweep (a single rebase task naming every stale PR),
never as one task per PR, and no step may refer forward with "read step X first".

#### Scenario: stale PRs are swept as one task before the backlog

Given an open PR set where `stale > 0`,
when the tick orders its steps,
then a single board-wide rebase task naming every stale PR precedes any new
backlog dispatch, and a DIRTY PR (which gets no CI run) is assigned an owner.

### Requirement: the prompt and script are versioned with a live-vs-tree drift gate

The running `jobs.json` prompt and the measurement script must be versioned under
`agents/llgenie-planner/`, and a gate must red when the live prompt diverges from
the versioned copy. The gate is host-only: it runs where the live `jobs.json`
exists.

#### Scenario: the live prompt matches the versioned copy

Given a host with the live `jobs.json` whose prompt equals the versioned `cron/llgenie-orchestrator-tick.md`,
when `make check-tick-prompt` runs,
then it exits 0 and prints the byte count.

#### Scenario: the live prompt diverges

Given a host whose live `jobs.json` prompt differs from the versioned copy,
when `make check-tick-prompt` runs,
then it exits 1 and names both byte counts.

### Requirement: the 2026-11-08 board state is reproducible from fixtures

The measurement must reproduce the 2026-11-08 recorded totals (`open=14 stale=12
dirty=2`, `idle_non_planner=7`) from fixture inputs, so the accounted-offset is
not a one-off sighting.

#### Scenario: feeding the 2026-11-08 PR and kanban fixtures

Given the recorded 2026-11-08 PR list and kanban state as fixtures,
when `tick_board.sh` runs against them with the same main sha,
then section B prints `TOTAL open=14  stale=12  dirty=2` and section C prints
`idle_non_planner=7`.
