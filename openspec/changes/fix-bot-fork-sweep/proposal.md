# fix-bot-fork-sweep

## Why

`scripts/fix_bot_sweep.py` selects only PRs whose head is in the base repository, and
`.github/workflows/fix-bot.yml` pushes to `origin`. Every llgenie PR is opened from the fork
(`andyholst:feat/...`, AGENTS.md's PR rule), so the scheduled sweep passes over every real PR:

```
$ make fix-bot-sweep DRY=1 REPO=asimov-agent/llgenie
[sweep] skip #170 (...): a fork (andyholst)
[sweep] skip #336 (...): a fork (andyholst)
[sweep] skip #337 (...): a fork (andyholst)
[sweep] nothing to fix among 3 open PR(s)
```

Eight consecutive scheduled runs were green and did nothing, so a red PR is never repaired by
the bot. The sibling `rebase-bot-sweep` already solved this with `--own-fork`.

Issue: [#340](https://github.com/asimov-agent/llgenie/issues/340).

## What Changes

- `scripts/fix_bot_sweep.py`: an `--own-fork <owner>` allowlist (mirroring rebase-bot). A PR whose
  head is the base repo **or** that fork is eligible; any other fork stays skipped.
- `Makefile`: `fix-bot-sweep` forwards `OWN_FORK=`.
- `.github/workflows/fix-bot.yml`: the sweep passes `OWN_FORK=andyholst`; the fix job reads the
  PR's head repository, checks the branch out from that remote (`fork` when it is the allowlisted
  fork, `origin` otherwise), and pushes with `--force-with-lease` to the **PR's own head remote** —
  never to `main`, never to a fork the token cannot write.
- Tests: the real `choose()` selects an allowlisted fork PR and still skips another fork; the
  workflow's push targets the head remote.

## Impact

- Affected specs: `fix-bot-sweep` (modified).
- Affected code: `scripts/fix_bot_sweep.py`, `Makefile`, `.github/workflows/fix-bot.yml`,
  `tests/test_fix_bot_sweep.py`, README, `agent-wiki/`.
- Unchanged: the claim protocol, the attempt cap, the fix loop, the redaction seam.

## Not covered

- A PR from a third-party fork is still not repaired (the token cannot push it); #340 only
  allowlists the repository's own fork.
