# acceptance-gate-circular — proposal

Issue: [#2094](https://github.com/asimov-agent/llgenie/issues/2094)

## Why

`make check-pr-acceptance` (issue #1792: `scripts/check_pr_acceptance.py`) can classify an issue's
unticked `## Acceptance criteria` criterion only as `acceptance-unchecked` (a red, blocking finding).
But a criterion of the shape *"the PR that fixes it is green in CI on the same job that failed"* is
UNSATISFIABLE when that job is the acceptance gate's own (`guard` running `check-pr-acceptance`, or
the `ci-verdict`/`judge`/`ci-scope-decision` chain the `guard` gates): the gate cannot pass until the
criterion is ticked, and the criterion cannot be proven until the gate passes. Measured 2026-11-08
(item 2 of #2046 on PR #2051): the `guard` failed `check-pr-acceptance` on item 2, `linux` was skipped
by `needs: [guard]`, `ci-verdict` published no `ci-scope-decision` artifact, so `judge` redded, and the
PR could never go green — `mergeStateStatus` stayed `BLOCKED`. Classification as `acceptance-unchecked`
parks a finished PR forever and forces reviewers into a false tick or waive (the #745/#1858 class this
gate exists to prevent).

## What Changes

- `scripts/check_pr_acceptance.py`: a criterion that demands the acceptance gate's OWN job verdict be
  green is classified `gate-circular` — a distinct, NON-blocking finding — instead of
  `acceptance-unchecked`. The detector (`_requires_own_gate_verdict`) matches the gate's own footprint:
  the unambiguous identifiers (`check-pr-acceptance`, `check-pr-acceptance-form`, `ci-verdict`,
  `ci-scope-decision`) always, and the `guard`/`judge` CI JOB names only when written as the job
  (`guard job` / `judge job`) so a product "quota guard" is never trapped. The finding's message names
  the loop and points to the authoring rule (a criterion must be provable by a run or command it does
  not itself gate) and the `## Not covered` + linked `#<n>` escape. `render()` labels the finding
  `[gate-circular]` (distinct from `proven-awaiting-writer`) and it never sets a BLOCKING flag, so a
  close whose peers are proven exits zero.
- `scripts/issue_body.py`: the `## Acceptance criteria` authoring rule is documented — a criterion must
  be PROVABLE by a run or a command it does not itself gate — on the renderer that writes the boxes.
- `docs/BOTS.md`: the `check-pr-acceptance` states paragraph gains the fourth (`gate-circular`) state.
- `tests/test_check_pr_acceptance.py`: pins the classification (guard-job criterion → `gate-circular`,
  non-blocking), the "close not red once peers proven" case, the render label, the negative controls
  (an ordinary unchecked criterion stays `acceptance-unchecked`; a product "guard" is never trapped),
  the `## Not covered` escape still winning, and the live CLI exiting zero on a gate-circular close.

## Benefit

A finished PR is not parked by its own definition of done: the acceptance gate recognises the closed
loop it creates (`gate-circular`) and never holds a close whose other criteria are proven, so
reviewers are no longer forced to false-tick or waive a box the gate itself blocks, and the board's
single largest failure class stops being a permanent deadlock.
