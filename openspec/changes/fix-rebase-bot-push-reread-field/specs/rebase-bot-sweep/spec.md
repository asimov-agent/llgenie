# rebase-bot-sweep

## MODIFIED Requirements

### Requirement: the push-time dead-vehicle re-read uses fields gh pr view exposes and surfaces stderr

The push-time dead-vehicle re-read (issue #1733) runs `gh pr view` right before the
force-push. The invocation MUST request only `--json` fields `gh pr view` actually exposes:
`state,mergedAt` — never `merged`, which gh rejects with `Unknown JSON field: "merged"` rc=1 on
EVERY call (issue #1965). `state` is the open/closed/merged vocabulary and `mergedAt != null`
is the merged boolean; `state` MUST be lowercased (`.state|ascii_downcase`) before the
`!= "open"` comparison, because gh returns it UPPERCASE (`OPEN`). Any rc=1 is retried up to 3
times; each retry MUST surface the read's stderr in the run log so a mis-arg / auth /
rate-limit / relay fault is named, not masked behind a bare rc. A read that still fails after
3 attempts, or that answers a confirmed closed/merged state, MUST stop the run with a
`gave-up` comment and no push — the fail-closed refusal (issue #1733) is NOT weakened.

WHEN the push-time `gh pr view` is issued with the dead `--json state,merged` spelling
THEN it must fail closed (no push) AND the run log names the `Unknown JSON field` error.

#### Scenario: a permanent re-read argument error is attributed and still refuses the push
- **Given** a rebase that reached the push-time re-read and a `gh pr view` that keeps failing
  the field validation (`merged` is not a field the fake gh exposes)
- **When** `scripts/rebase_bot.sh` runs
- **Then** it exits non-zero with a `gave-up` refusal, no `--force-with-lease` push fires, the
  branch is untouched, and the run log surfaces the `Unknown JSON field` error text the real
  gh emits
- **Test:** `tests/test_rebase_bot_sweep.py::test_a_permanent_read_argument_error_is_attributed_and_still_refuses`

### Requirement: a transient push-time re-read fault is retried, a persistent one still refuses

The push-time dead-vehicle re-read (issue #1733) runs `gh pr view --json state,mergedAt` right
before the force-push. A SINGLE transient fault (rc=1 or an empty relayed answer) MUST be retried
up to 3 times so one glitch does not redden the whole sweep (the #1602/#1603 discipline). A read
that still fails after the retries, or that answers a confirmed closed/merged state, MUST stop the
run with a `gave-up` comment and no push — the fail-closed refusal is NOT weakened.

WHEN the push-time `gh pr view` faults transiently
THEN the actor retries it; a later successful read lets the push proceed and the branch is
force-pushed to the PR's head remote.

#### Scenario: a transient push-time read fault is retried and the branch is pushed
- **Given** a rebase that reached the push-time re-read and a `gh pr view` that faults once
  (rc=1) then answers open/unmerged
- **When** `scripts/rebase_bot.sh` runs
- **Then** the retry succeeds, the branch is force-pushed to the head remote, and the run exits 0
- **Test:** `tests/test_rebase_bot_sweep.py::test_a_transient_push_time_read_fault_is_retried_not_fatal`

#### Scenario: a persistently unreadable PR is still refused
- **Given** a rebase whose push-time `gh pr view` keeps faulting through all 3 attempts
- **When** `scripts/rebase_bot.sh` runs
- **Then** it exits non-zero with a `gave-up` refusal, no push fires, and the branch is untouched
- **Test:** `tests/test_rebase_bot_sweep.py::test_a_persistent_push_time_read_fault_still_refuses`
