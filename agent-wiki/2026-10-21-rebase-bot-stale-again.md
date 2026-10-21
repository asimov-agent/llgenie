# 2026-10-21 — eligibility is the merge state, not "already rebased today" (issue #467)

## What was wrong

The drain loop was live, but a dispatch (run 39590567679) rebased nothing:

```
[rebase-bot] pass-over: #447 was already rebased today
[rebase-bot] pass-over: #448 was already rebased today
stop: the sweep answered 'none' after 0 rebase(s)
```

#447 and #448 were `CONFLICTING`/`DIRTY` at that moment: they had been rebased earlier in the day
and `main` moved afterwards (#458/#461/#463). `rebased_today()` was consulted before the merge
state, so a PR that needed another rebase waited for the UTC date to roll over.

## What changed

- `scripts/rebase_bot_sweep.py`: no early "already rebased today" pass-over — today's markers only
  bound the daily cap. A new `skip` / `--skip` list passes over the PRs **this run** already
  rebased, so one run cannot loop on the same PR.
- `.github/workflows/rebase-bot.yml`: the loop accumulates the PRs it rebased and passes `SKIP=`.
- `Makefile`: `rebase-bot-sweep` forwards `SKIP=` as `--skip`.

## Verified

- `pytest tests/test_rebase_bot_sweep.py tests/test_bot_decision_loudness.py` 40 passed: a
  re-dirtied PR is picked, `--skip` is respected, the loop forwards the list, and a `rebased`
  marker still counts toward the cap while a claim/`gave-up` does not.
- Read against the LIVE repo with the fixed code: `sweep(skip=[])` -> `action=rebase pr=447
  state=DIRTY` (the PR the 07:06Z run passed over), and `sweep(skip=[447])` ->
  `pr=448` with `#447 was already rebased in this run` — the drain behaviour, measured.
- Structural gates and the full suite recorded in the PR.

## Status

Issue #467; PR #468 from `feat/rebase-bot-stale-again` against `asimov-agent/llgenie:main`. Waiting for
review — the agent never merges.
