# Spec delta: stalled-run-cancel-policy (issue #2997)

## ADDED Requirements

### Requirement: a stalled run named by the watchdog is cleared by a gated cancel

When `scripts/stalled_job_watchdog.py` runs with `--cancel-stalled`, every run it classifies as
stalled (at least one CONCLUDED job plus an `in_progress` job past the budget
`max(STALL_FLOOR, STALL_FACTOR x median job-name wall time)`, fallback `FALLBACK_MINUTES`) MUST be
cancelled via `gh run cancel`, subject to the proofs below. The cancel reuses the watchdog's own
classification — the policy adds no threshold and no new detection class.

#### Scenario: a cancelled stalled run gets a classified verdict, not silence

- **Given** a PR-head run classified stalled and cancelled by the watchdog
- **When** the cancelled run completes as `conclusion=cancelled`
- **Then** `ci-verdict` reads the head through its blocking-conclusion path and posts its neutral
  verdict at that head, and `auto_merge` defers the merge because `cancelled` is in its
  RED_CONCLUSIONS — the wedge ends with a named, tested verdict instead of a missing one

#### Scenario: a job that concluded between classification and cancel is never cancelled

- **Given** a classified stalled run whose stalled job re-read immediately before the cancel has
  concluded (the run finally progressed)
- **When** the watchdog runs with `--cancel-stalled`
- **Then** the cancel is skipped for that run and the report names it as skipped, so a live job is
  never touched (the #1822/#1823 rule)

#### Scenario: a cancel that races a conclusion is benign

- **Given** a classified stalled run that GitHub had already concluded before the cancel landed
- **When** `gh run cancel` answers that the run is completed
- **Then** the outcome is reported as a benign race, not a delivery failure (the #1410 precedent)

### Requirement: only PR-head runs are cancellable

The watchdog cancels only a stalled run whose head branch carries an OPEN, non-draft pull request. A
stalled run with no PR — a push, a schedule, or a `main`-lane run — is named in the report only.
Clearing non-PR runs stays the domain of the zero-job (#1410) and frozen-reaper lanes.

#### Scenario: a stalled schedule run is named, never cancelled

- **Given** a classified stalled run on a schedule trigger with no pull request
- **When** the watchdog runs with `--cancel-stalled`
- **Then** the run appears in the report and no `gh run cancel` is invoked for it

### Requirement: the cancel never starts a pipeline

The watchdog's cancel action MUST NOT dispatch, rerun, or requeue anything, and MUST NOT post any
comment or check whose effect is a new run. It ends runs; recovery after a cancel arrives only
through GitHub events (push, PR synchronize, label) or a human.

#### Scenario: a cancelled head is not re-run by the watchdog

- **Given** a head whose stalled run was cancelled by the watchdog
- **When** the watchdog's next monitor pass runs
- **Then** no `gh run rerun`, `workflow_dispatch`, or re-trigger is issued for that head, and the
  next run at it is whatever a GitHub event or a human produces

### Requirement: the unattended lane carries the clearing action behind an explicit knob

`make check-stalled-jobs` MUST translate `CANCEL=1` into `--cancel-stalled` by reference in the
recipe (the `FILE`/`CANCEL` knob style of `check-zero-job-pending`), and
`.github/workflows/zero-job-pending.yml` MUST pass the knob through the existing watchdog step on
the existing lane trigger — no new workflow, no new schedule.

#### Scenario: the knob is off by default

- **Given** the watchdog step running without `CANCEL=1`
- **When** it classifies a stalled run
- **Then** the run is named (and filed with `FILE=1`) but NOT cancelled — cancellation requires the
  explicit knob on the lane
