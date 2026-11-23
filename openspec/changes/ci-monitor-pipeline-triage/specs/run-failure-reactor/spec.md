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
