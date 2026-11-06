# trigger-subprocess-deadline-bound

## ADDED Requirements

### Requirement: each trigger subprocess is bounded so a stalled gh cannot hold the gate past its `DEFAULT_MAX_WAIT`

The trigger's `_sh` and `_gh` helpers and the `gh workflow run` dispatch MUST cap each subprocess at
`SUBPROCESS_TIMEOUT` seconds. On `TimeoutExpired`, `_sh`/`_gh` MUST return `""` (no verdict) and the
dispatch MUST fall through to run discovery, so the poll loop's own `DEFAULT_MAX_WAIT` deadline
remains the authoritative bound and the gate fails with a clear message rather than hanging.

WHEN a `gh`/shell subprocess stalls longer than `SUBPROCESS_TIMEOUT`
THEN the call returns `""` / continues promptly, and the `time.time() > deadline` check decides.

#### Scenario: a stalled subprocess returns promptly with ""

- **Given** `_sh` with a subprocess that sleeps past `SUBPROCESS_TIMEOUT`
- **When** the call is invoked
- **Then** it returns `""` in ~`SUBPROCESS_TIMEOUT` seconds, not after the child's full sleep
- **Test:** `tests/test_engine_build_trigger.py::test_a_stalled_gh_call_cannot_hold_the_poll_past_its_deadline`
  monkeypatches `SUBPROCESS_TIMEOUT` to 1s and asserts a sleep-10 child returns `""` in under 5s

### Requirement: the existing verdict logic and error message are unchanged

The change MUST NOT alter what the gate checks, only how it gives up on a stalled call: the
`DEFAULT_MAX_WAIT` deadline, the clear failure message, and run-discovery behavior stay as today.

WHEN no subprocess stalls
THEN the trigger behaves exactly as before the cap

#### Scenario: non-stalled calls are unchanged

- **Given** a trigger poll whose `gh`/shell calls each complete within `SUBPROCESS_TIMEOUT`
- **When** the poll loop runs
- **Then** it dispatches, polls, and reports exactly as before the cap — same verdicts, same messages
