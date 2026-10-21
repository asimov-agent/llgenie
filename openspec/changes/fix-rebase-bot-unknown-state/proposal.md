# fix-rebase-bot-unknown-state

## Why

Run `39553726935` (2026-10-21T06:09Z) shows the rebase-bot passing over the three PRs that
actually needed it:

```
[rebase-bot] pass-over: #445 is UNKNOWN against main
[rebase-bot] pass-over: #446 is UNKNOWN against main
[rebase-bot] pass-over: #447 is UNKNOWN against main
[rebase-bot] #448 is DIRTY against main
action=rebase
```

Minutes later GitHub reports all three as `CONFLICTING` / `mergeStateStatus: DIRTY`. The sweep
treats `UNKNOWN` ("mergeability not computed yet") as "does not need rebasing", so a 6-hourly
run can repeat that observation and those branches stay stale forever. The same run also shows
`[rebase-bot] could not comment`: the `Rebase it …` step has no `GH_TOKEN`, so the outcome
comment — and the `done` marker the sweep and the other bots read — never posts.

Issue: [#453](https://github.com/asimov-agent/llgenie/issues/453).

## What Changes

- `scripts/rebase_bot_sweep.py`: a PR whose `mergeStateStatus` is `UNKNOWN` is **re-resolved**
  through `gh pr view <n> --json mergeStateStatus` (bounded: `UNKNOWN_ATTEMPTS` re-queries with a
  small delay, both overridable) before the pick is decided. A resolved `BEHIND`/`DIRTY` is taken.
  A PR that is still `UNKNOWN` is reported as **deferred**, with the reason naming it and the
  next run as the retry — never silently filed under "does not need rebasing".
- `.github/workflows/rebase-bot.yml`: the `Rebase it …` step exports `GH_TOKEN: ${{ github.token }}`
  so `scripts/rebase_bot.sh`'s outcome comment and its `done` marker are actually written.
- Hermetic tests in `tests/test_rebase_bot_sweep.py`: UNKNOWN→DIRTY is picked, a permanently
  UNKNOWN PR is deferred by name, and the workflow step carries the token.

## Impact

- Affected specs: `rebase-bot-sweep` (modified).
- Affected code: `scripts/rebase_bot_sweep.py`, `.github/workflows/rebase-bot.yml`,
  `tests/test_rebase_bot_sweep.py`, README (rebase-bot section) and an `agent-wiki/` entry.
- No change to the rebase actor, the conflict hand-off, or the push/lease behaviour.

## Not covered

- The `make lint` failure inside `scripts/rebase_bot.sh`'s structural gate (the runner has no
  `llgenie/test:latest`, so lint fails and is non-fatal there) — a separate finding, filed on its
  own, not folded into this fix.
