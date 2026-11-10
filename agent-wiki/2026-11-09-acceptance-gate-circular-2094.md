# the acceptance gate classifies a self-gating criterion as gate-circular (issue #2094) — 2026-11-09

**Implements:** issue #2094 — an acceptance criterion of the shape *"the PR that fixes it is green in
CI on the same job that failed"* is UNSATISFIABLE when that job is the acceptance gate's own (`guard`
running `make check-pr-acceptance`, or the `ci-verdict`/`judge`/`ci-scope-decision` chain the `guard`
gates). Measured 2026-11-08 on #2046 (PR #2051): `guard` failed `check-pr-acceptance` on item 2,
`linux` was skipped by `needs: [guard]`, `ci-verdict` published no `ci-scope-decision` artifact, so
`judge` redded, and the PR could never go green — `mergeStateStatus` stayed `BLOCKED` and reviewers were
forced into a false tick or waive. `make check-pr-acceptance` could classify an unticked criterion only
as `acceptance-unchecked` (blocking), which parked a finished PR forever on its own definition of done.

## What changed

- **`scripts/check_pr_acceptance.py`** — a criterion that demands the acceptance gate's OWN job verdict
  be green is classified `gate-circular` — a distinct, NON-blocking finding with a message naming the
  loop — instead of `acceptance-unchecked`. The detector `_requires_own_gate_verdict()` matches the
  gate's own footprint: the unambiguous identifiers `check-pr-acceptance`, `check-pr-acceptance-form`,
  `ci-verdict`, `ci-scope-decision` always, and the `guard`/`judge` CI JOB names only in the `guard job`
  / `judge job` form, so a product "quota guard" is never trapped. `render()` labels the finding
  `[gate-circular]`, and it never sets `blocking` — a close whose peer criteria are proven exits zero.
  The `## Not covered` + linked `#<n>` exemption (`_declared_out_of_scope`) still wins when present.
- **`scripts/issue_body.py`** — `_criteria` documents the authoring rule: a criterion must be PROVABLE
  by a run or a command it does not itself gate.
- **`docs/BOTS.md`** — records the fourth `check-pr-acceptance` state (beside unproven-red,
  proven-awaiting-writer, out-of-scope).
- **`tests/test_check_pr_acceptance.py`** — seven new hermetic tests: the classification, the
  close-not-red-once-peers-proven case, the render label, the negative controls (an ordinary unchecked
  criterion stays `acceptance-unchecked`; a product "guard" is never trapped), the `## Not covered`
  escape, and the live CLI exiting zero on a gate-circular close.
- **`openspec/changes/acceptance-gate-circular/`** — the required OpenSpec change
  (proposal + spec + tasks).

## Decisions

- **The gate recognises its own loop rather than requiring a body edit.** The PR-body `## Not covered` +
  linked `#<n>` seam remains the sanctioned escape, but a lane that hits a self-gating criterion no
  longer has to hand-edit another lane's PR body — the gate names the loop itself and holds nothing.
- **Non-blocking by construction.** A `gate-circular` criterion is unprovable while the gate is its own
  prerequisite, so it can never hold a close whose peers are proven — this is what unwedges the board's
  largest failure class without weakening any genuinely-provable criterion (those still red).
- **Scoped to the gate's own footprint.** `guard`/`judge` count only as the CI JOB (`guard job` /
  `judge job`); a product noun like a "quota guard" is never trapped. Proved by a negative control.
- **Proved the guard catches the bug:** on `origin/main` the self-gating criterion reds
  `acceptance-unchecked`; at this head it is `gate-circular` (run on both trees).

Refs: #2094 (this issue), #1792 (the acceptance gate), #2046/PR #2051 (the measured deadlock),
#745/#1858 (a tick must be provable), #1644 (the verdict-gated write-back).
