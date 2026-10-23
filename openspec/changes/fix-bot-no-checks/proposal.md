# A PR with no checks is not a red PR

## Why

`scripts/fix_bot_sweep.py::failing_checks()` calls `gh pr checks --json …` and treats ANY non-zero exit as a
crash. `gh pr checks` exits non-zero for a branch whose workflows never ran:

```
RuntimeError: gh pr checks 527 --repo asimov-agent/llgenie --json name,state,bucket,workflow failed:
              no checks reported on the 'agent/architecture-20261022T1842' branch
make: *** [Makefile:661: fix-bot-sweep] Error 1
```

Measured twice — run `39884199020` (2026-10-23T01:28) and `39863859921` (2026-10-22T22:17) — on PR #527, which
was opened with `GITHUB_TOKEN` and therefore has no checks at all (#497). The sweep dies on the FIRST such PR,
so no other PR can ever be repaired that sweep; the `fix` job is then skipped (its `needs:` failed).

## What Changes

- `failing_checks()` treats the `no checks reported` answer as **nothing red** (an empty list) and keeps
  raising on every other `gh` failure, so a genuinely unreadable API still turns the run red.
- A regression test drives the real sweep against a fake `gh` that exits 1 with that exact message, and
  asserts the sweep skips the PR and finishes (`nothing to fix among 1 open PR(s)`).

## Impact

- The fix-bot sweeps past a check-less PR instead of dying on it, so it can reach the PRs it is meant to
  repair.
- An unrelated `gh` failure is still loud — the guard narrows to one message, it does not swallow errors.
