# Proposal: agents-debt-analysis-issue-only

Issue: #231

## Why

Fixing the registry-sync gate (#223) surfaced four *separate* problems — the
engine-ranking rule (#225), the scope/filter question (#227), the per-engine
list + matrix coverage (#228), and the unskilled-engine gap (#229). They were
found only because the fix was examined past its symptom, and they were filed as
their own issues rather than folded into the PR.

That is the behaviour we want to be routine, not incidental: the codebase grows
on every sync (#179), so silent drift in ranking, catalog cells and engine
coverage accumulates unless every change is also read as a signal about what is
now inaccurate, untested or worth refactoring. Today nothing in `AGENTS.md`
requires it.

## What Changes

- `AGENTS.md` gains a durable rule — **"Analysis: every change surfaces gaps →
  issues, never implementation"**: every change MUST be analysed for real gaps
  and technical debt; each demonstrable finding MUST be filed as its own detailed
  issue (evidence, why, what "done" is), linked both ways, and MUST NOT be
  implemented inside the current change or left as prose.
- A test (`tests/test_agents_debt_analysis.py`) asserts the rule is present in
  `AGENTS.md`, wired into `make test-unit`, so it cannot be dropped silently
  (mirroring `tests/test_agents_worktree.py` from #217).

Docs + test only: no product behaviour change.

## Out of scope

The findings themselves. The first application items — whether the trending list
is accurate given how llgenie behaves, and the `model_engine_pick.py` refactors
(one ~1200-line module mixing ranking, planning, download and registry IO; no
per-engine artifact) — are filed as separate issues, not fixed here.

## Impact

`AGENTS.md`, `tests/test_agents_debt_analysis.py`, `Makefile` (test-unit list).
