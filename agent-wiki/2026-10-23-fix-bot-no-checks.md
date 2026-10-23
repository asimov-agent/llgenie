# 2026-10-23 — a PR with no checks does not kill the fix-bot sweep (#496)

**Issue:** [#496](https://github.com/asimov-agent/llgenie/issues/496) · **PR:** the PR that closes it

## What was wrong

`failing_checks()` in `scripts/fix_bot_sweep.py` called `gh pr checks --json …` and treated any non-zero exit as
a crash. `gh pr checks` exits non-zero for a branch whose workflows never ran — `no checks reported on the
'<branch>' branch` — so the sweep died on the first such PR, and the `fix` job was skipped behind its failed
`needs:`.

Measured twice on PR #527 (opened with `GITHUB_TOKEN`, so it has no checks at all — #497):

```
run 39884199020 (2026-10-23T01:28)  RuntimeError: gh pr checks 527 … no checks reported on the 'agent/architecture-20261022T1842' branch
run 39863859921 (2026-10-22T22:17)  same
```

## What changed

- `failing_checks()` returns `[]` when the error is that message, and still raises for anything else, so an
  unreadable API stays loud.
- The fake `gh` in `tests/test_fix_bot_sweep.py` can now answer "no checks reported", and one regression test
  drives the real sweep: it skips #527, finishes with `nothing to fix among 1 open PR(s)`, exit 0.

## Verified

- `pytest tests/test_fix_bot_sweep.py` in `llgenie/test:latest` → 15 passed.
- `make lint`, `make check-docs`, `make check-wiring`, `make check-workflows`,
  `make openspec-validate NAME=fix-bot-no-checks` → green; `make test-unit` in the PR checks.

## Fleet context (the audit that found it)

The fix-bot was the only bot whose *sweep* was red; the others' most recent runs are green and acting:
architecture-bot (refreshed `docs/ARCHITECTURE.md`, #527 merged), auto-merge (merged #530 and #532 itself),
issue-bot, issue-refiner, rebase-bot, run-failure-reactor, queued-alarm, search-smoke, publish-agent-image,
engine-bump-rebase. Still red and tracked separately: `engine-bump`'s `bump-strata` leg and `registry-sync`
(the known upstream registry loss), plus #522 (a refine parks an issue) and #515 (no `--json` field guard).
