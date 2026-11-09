# The orchestrator tick prompt gains an AC8 STATUS SELF-AUDIT sub-step — versioned live→tree (issue #2366, closes #2136-family)

## What changed

Issue #2083's AC8 required that a pass which finds an overdue tick, a disabled tick, or no tick
fired for more than one interval report it as a **fleet outage** in its own report — never as lane
idleness. The landing edit went live only (a STEP 1 `STATUS SELF-AUDIT` sub-step forcing a
`FLEET OUTAGE: tick overdue/disabled` opening line), which is the exact failure class issue #2136
exists to prevent: a live-only prompt change that never reaches the tree lets a profile rebuild
restore the old, outage-blind instruction while `make check-tick-prompt` (a host-only gate) cannot
see the drift from CI.

This PR re-snapshots the live orchestrator tick prompt (`cc5d2bd4083a`) live→tree into
`agents/llgenie-planner/prompts/llgenie-orchestrator-tick.md` **verbatim** so the tree mirrors the
running scheduler contract. Measured at the head:

- live `jobs.json` prompt for `cc5d2bd4083a` = 19,210 chars (on-wire re-read this pass)
- `make check-tick-prompt` → `OK live prompt == versioned (19210 b)`, rc 0 — the drift gate is green
- the new AC8 STEP 1 `STATUS SELF-AUDIT` sub-step (`FLEET OUTAGE` phrase) is present in the
  committed copy and still present, unchanged, in the live job

The re-snapshot is additive vs the prior versioned copy **modulo the older live-ahead steps already
pending in issue #2358**: this PR carries those older steps too (the renumbering out of STEP 6c→6d,
the `/tmp` worktree collector from #2141, the engine-domain map, the verify-lane-contract live path)
because the gate demands `versioned == live` byte-for-byte, and #2358 is the separate vehicle that
already documents them. The NEW behaviour this issue names is only the AC8 `STATUS SELF-AUDIT`
sub-step. The live `jobs.json` prompt is left untouched — the AC8 live edit was already applied and
verified by the orchestrator work on #2083, so this PR is repo-side versioning only.

## Reference

- #2083 — the scheduler-contract issue: AC8 required the outage-reporting rule; closed COMPLETED
  with the live sub-step landed.
- #2366 — this repo-side half: version the live AC8 sub-step live→tree + change-note trio.

## Verification

- `make check-tick-prompt` → `OK live prompt == versioned (19210 b)`, rc 0 at the head.
- `make -s lint check-docs check-wiring check-pr-authors check-issue-bodies check-pr-hygiene` → rc 0
  at the head.
- The committed prompt was copied byte-for-byte from the live `jobs.json` (`cc5d2bd4083a`) value,
  with exactly one trailing newline added (the drift gate's instrument strips it before comparing).
