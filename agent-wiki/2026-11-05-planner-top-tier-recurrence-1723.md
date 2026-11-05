# Planner: pinned the tracked #1723 top-tier recurrence at the new merge tip

Date: 2026-11-05 · planner lane · change-note (sanctioned tracked path #1103/#1725-style)

## What happened

After **#1732 merged (`b85901726`)**, the fleet's `linux / top-tier (run)` gate failed
at the new main tip — **run 41939115306, job 126955674736**, failing
`tests/test_top_tier_acceptance.py:321`:

```
assert sizes == sorted(sizes, reverse=True), f"{owner} picks must be high->lower"
AssertionError: ccore picks must be high->lower
assert [4482402816, 4482402848] == [4482402848, 4482402816]   # index 0 diff
```

This is the **#1723 class** — the deterministic per-provider ordering defect in
`scripts/llgenie_serve.py::discover_top_tier` where near-identical 32-byte tier
boundaries come back out of order. It recurs on **every main tip** because the fix
branch (`fix/top-tier-per-provide`) has **never landed despite six dispatches**.

## What the planner did (measured, not assumed)

1. Polled the #1732 post-merge matrix at `b85901726` to conclusion: guard, verdict,
   ci-images, liveness, recheck, agents-read, cpu-health, install, lint, openspec,
   scanner-images all SUCCESS; **`linux/top-tier (run)` = FAILURE** (completed
   00:13:01Z); `linux/unit` in_progress.
2. Read the failing job's log and confirmed it is the **same #1723 assertion snippet**,
   not an assumed recurrence (`E AssertionError: ccore picks must be high->lower`).
3. **Pinned the fresh run** on the canonical tracker #1723 (comment **6645905877**)
   carrying run 41939115306 + job 126955674736 + base `b85901726`.
4. **Re-dispatched the implementer** onto base==`b85901726` (body `AGENTS: b85901726`,
   `closes #1723`) with a done-proof of a *completed green* `linux/top-tier` at that
   base — and explicitly "DO NOT weaken `test_top_tier_acceptance.py:321`".

## Lesson

A pre-existing tracked class that recurs at **every new merge tip** is the strongest
signal the fix is the blocker. The planner's task-relative duty when that happens is to
**re-pin the fresh run id + base and re-dispatch**, not to end the pass "waiting on
top-tier". Measure the recurring class's log, name the run, re-anchor the fixer, record
it. Committed to the planner's merged-PR stale-rebase guard reference.
