# Spec delta: host-ci-monitor (issue #3049)

## ADDED Requirements

### Requirement: the monitor sweep re-reads every reactor-filed main-red issue with the incident rule

A make target MUST re-classify every OPEN issue carrying the run-failure reactor's filing marker (the
marker IS the filing — the reactor's own dedupe key; the `agent:ci-pipelines-maintainer` label is
recorded on the verdict, never required, because a filing can carry no label at all: measured on #3044)
against the same rule `scripts/ci_monitor.py` uses after
issue #3048: a failure is live only when the filing workflow's NEWEST completed run on `main` is
itself `failure`/`cancelled`/`timed_out`. The sweep MUST reuse `classify_main_runs()` rather than
re-implement the ordering, so the printed incident set and the re-triage verdict cannot diverge. One
verdict line per re-read issue: `SWEEP issue=<n> workflow=<name> run=<id> superseded-by <run>` or
`SWEEP issue=<n> workflow=<name> run=<id> live newest-red=<run>`. A workflow with no completed `main`
run after the filing MUST be reported `no-newer-run` and left open, never inferred.

#### Scenario: a superseded filing is named with its superseder

- **Given** an open reactor-filed issue naming run `45259560508` of workflow `ci-frozen-reaper`
- **And** a newer completed `main` run of that workflow concluded `success`
- **When** `make -s monitor-triage-sweep` (dry) prints the verdicts
- **Then** the line reads `superseded-by <newer run id>` and no other verdict wording appears for it
- **Test:** `pytest tests/test_monitor_triage_sweep.py -q` (no network)

#### Scenario: a still-red workflow stays live and names the current red run

- **Given** an open reactor-filed issue whose workflow's newest completed `main` run is a `failure`
  different from the run the issue names
- **When** the sweep prints the verdicts
- **Then** the line reads `live newest-red=<newest red run id>` and the issue is not closed
- **Test:** `pytest tests/test_monitor_triage_sweep.py -q` (no network)

### Requirement: the sweep writes only to the issues it owns and never to a pipeline

The sweep's write half MUST be opt-in (`--apply`; the default is dry) and MUST act only through the
issue side: a `scripts/bot_claims.py` claim comment before acting, a comment naming the superseder run
on a superseded issue, `gh issue close` on that issue only, and a comment recording the current red run
on a live filing — a filing whose current red run id already appears on the issue, in its body **or in a
comment an earlier pass wrote**, gets no second comment, so re-running the sweep never stacks the same
verdict on the same issue
on a live issue. It MUST NOT rerun, re-dispatch, cancel or merge a pipeline, and MUST NOT dispatch a
fix-bot (AGENTS.md: queue-pumping is forbidden; the host files tracked issues and dispatches nothing).

#### Scenario: dry mode touches nothing

- **Given** a dry sweep over open reactor-filed issues
- **When** the sweep finishes
- **Then** every `gh` call it made is a read (`issue list`, `issue view`, `run list`, `run view`) and no
  comment or close was issued
- **Test:** `pytest tests/test_monitor_triage_sweep.py -q` asserting the recorded argv has no
  `comment`/`close` and no `rerun`/`cancel`/`dispatch`/`merge` verb

#### Scenario: apply closes a superseded filing with its evidence

- **Given** `--apply` and an issue whose verdict is `superseded-by 45304398388`
- **When** the sweep acts
- **Then** it posts a claim comment, then a comment naming `45304398388` as the superseder, closes that
  issue, and leaves every live verdict's issue open
- **Test:** `pytest tests/test_monitor_triage_sweep.py -q`

### Requirement: the re-triage is a wired, repeatable target

`mk/bots.mk` MUST expose the sweep as `monitor-triage-sweep` (host-only; `APPLY=1` opts into the
writes) so the sweep can be re-run after every monitor-rule change, and MUST print a final tally line
so a reader can tell how many issues were re-read, closed, kept, and skipped by a live claim.

#### Scenario: the target exists and reports a tally

- **Given** the repository after this change lands
- **When** `make -s monitor-triage-sweep` runs on the host
- **Then** it exits 0, prints one `SWEEP …` verdict per re-read issue and a final
  `SWEEP-TALLY re-read=<n> superseded=<n> live=<n> no-newer-run=<n> skipped-claim=<n>` line
- **Test:** recorded proof in the issue/PR body from `make -s monitor-triage-sweep`
