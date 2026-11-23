# Spec delta: run-failure-reactor (issue #3019)

## ADDED Requirements

### Requirement: `--file-only` files a Route-A failure instead of dispatching the fix-bot

`scripts/run_failure_reactor.py` MUST accept `--file-only`. With it, a failed run whose PR head is
pushable (Route A today dispatches the fix-bot) is routed as Route B: exactly one deduped issue via
the SAME marker search (`run-fixer: WORKFLOW/STEP`), the SAME `issue_body.render`, the SAME
lane-label classification, and the same "still work that is still work" supersession verdict. The
verdict line MUST name the override (`file-only: <route A target> -> filed|deduped|superseded`).
`--file-only` MUST dispatch nothing (no `gh workflow run`, no claim write for a dispatch subject).
Without the flag the existing routes are byte-identical.

#### Scenario: a pushable PR head is filed, not dispatched, under --file-only

- **Given** a recorded failed `pull_request` run whose head is a pushable same-repo PR
- **When** the reactor runs with `--file-only` against recorded seams
- **Then** it prints the filed/deduped verdict naming the override, calls the same issue-filing path
  once, and calls no dispatch path
- **Test:** `tests/test_run_failure_reactor.py` (recorded seams, rc=0)

#### Scenario: default routes are unchanged without the flag

- **Given** the same recorded run
- **When** the reactor runs WITHOUT `--file-only`
- **Then** the recorded fix-bot dispatch call happens as before
- **Test:** `tests/test_run_failure_reactor.py` (existing tests keep passing unchanged)

### Requirement: in-tick filing memory backs the lagged marker search

The reactor MUST keep a process-local set of markers it has already filed this process. The marker
search (`gh issue list --search`) is the memory ACROSS ticks, but GitHub's issue index lags a
just-filed issue by seconds — so a batch that routes several runs through ONE process (the monitor
triage) cannot see its own filing made moments earlier and would double-file one failure class
(measured 2026-11-23: #3020 and #3021 from one marker). A repeat of a marker already filed in this
process MUST print `already filed this tick` and file nothing.

#### Scenario: two runs of one class in one process file one issue

- **Given** two failed runs of the same marker class and a search that sees nothing filed (the lag)
- **When** one process routes the class twice, file-only
- **Then** exactly one `issue create` happens and the second routing prints the in-tick verdict
- **Test:** `tests/test_run_failure_reactor.py::test_two_runs_of_one_failure_class_file_one_issue_per_tick`
