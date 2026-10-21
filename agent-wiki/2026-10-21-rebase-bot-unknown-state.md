# 2026-10-21 — rebase-bot: decide from a COMPUTED merge state (issue #453)

## What was wrong

Run 39553726935 (2026-10-21T06:09Z) passed over exactly the PRs that needed a rebase:

```
[rebase-bot] pass-over: #445 is UNKNOWN against main
[rebase-bot] pass-over: #446 is UNKNOWN against main
[rebase-bot] pass-over: #447 is UNKNOWN against main
[rebase-bot] #448 is DIRTY against main
```

Minutes later all three read `CONFLICTING`/`DIRTY`. GitHub computes mergeability lazily, so the
sweep's `pr list` saw `UNKNOWN` and filed it under "does not need rebasing". The same run also
logged `[rebase-bot] could not comment` after a successful push: the `Rebase it …` step had no
`GH_TOKEN`, so the outcome comment (and the `done` marker the daily record and the other bots
read) never posted.

## What changed

- `scripts/rebase_bot_sweep.py`: `resolve_state()` re-asks a PR reported `UNKNOWN` through
  `gh pr view <n> --json mergeStateStatus`, bounded by `UNKNOWN_ATTEMPTS` (default 4) and
  `UNKNOWN_DELAY_S` (default 3s), both overridable (`--unknown-attempts` / `--unknown-delay`).
  A PR that never resolves is added to `result["deferred"]` and reported as deferred to the next
  run — never as "needs nothing".
- `.github/workflows/rebase-bot.yml`: the `Rebase it …` step exports `GH_TOKEN: ${{ github.token }}`.

## Verified

- `tests/test_rebase_bot_sweep.py` (23 tests): UNKNOWN→DIRTY is picked; a PR stuck at UNKNOWN is
  deferred by name; the actor step carries the token; the CLI passes the bounds. The fake `gh`
  now answers `pr view --json mergeStateStatus` from a per-PR state sequence, modelling the lazy
  computation.
- A read-only run of the real `sweep()` against `asimov-agent/llgenie` returns
  `action=rebase pr=445 state=DIRTY` — the exact PR the old code passed over as `UNKNOWN`.
- End-to-end retest with three real dispatches of the (unfixed, `main`) workflow:
  #445 and #447 now read `MERGEABLE` (both had been passed over as `UNKNOWN`); #446 picked,
  the agent could not resolve its conflict, nothing was pushed, and the report comment failed
  with `[rebase-bot] could not comment` — the second half of this fix, still unmerged.
- `make test-unit` -> 4943 passed, 6 deselected, exit 0.

## Status

OpenSpec change `fix-rebase-bot-unknown-state`; issue #453; PR #454 from `feat/rebase-bot-unknown`
against `asimov-agent/llgenie:main`. Waiting for review — the agent never merges.
