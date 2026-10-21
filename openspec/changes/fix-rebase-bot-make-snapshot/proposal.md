# fix-rebase-bot-make-snapshot

## Why

PR #446 cannot be rebased, and the model is not the reason — it never runs. Run `39566967551`
(08:09Z) shows the conflict resolution aborting before the agent:

```
Auto-merging Makefile
CONFLICT (content): Merge conflict in Makefile
CONFLICT (content): Merge conflict in README.md
[rebase-bot] conflict: asking the agent to resolve it
make[1]: Entering directory '/home/runner/work/llgenie/llgenie'
Makefile:628: *** missing separator.  Stop.
[rebase-bot] agent failed
```

`scripts/rebase_bot.sh` defaults `AGENT_CMD` to `make rebase-bot-agent`, invoked AFTER the
conflicted checkout; GNU make must parse `Makefile` before running any target, so a conflicted
Makefile stops it. The `rebase-bot-agent` recipe then runs `make _rebase-bot-agent` **inside the
container**, against the same conflicted file — a second, identical failure waiting to happen.

Issue: [#460](https://github.com/asimov-agent/llgenie/issues/460).

## What Changes

- `scripts/rebase_bot.sh` snapshots the Makefile **before** the checkout and invokes the agent
  through that snapshot: `make -f <snapshot> rebase-bot-agent`. Same target, same path — just a
  file that still parses while the tree is mid-rebase.
- The `rebase-bot-agent` recipe runs Hermes directly inside the agent image
  (`hermes -z "$(cat)" -m nous-deepseek --reasoning medium --yolo`, the shape
  `scripts/fix_loop.sh` already uses) instead of `make _rebase-bot-agent`, which would re-read
  the conflicted Makefile. The dead `_rebase-bot-agent` target is removed.
- Tests: the actor snapshots the Makefile and passes `-f`; the container command is the direct
  Hermes call and no longer invokes make; `_rebase-bot-agent` is gone.

## Impact

- Affected specs: `rebase-bot-sweep` (modified — the conflict hand-off).
- Affected code: `scripts/rebase_bot.sh`, `Makefile`, `tests/test_rebase_bot_sweep.py`, README's
  rebase-bot section, `agent-wiki/` entry.
- Unchanged: the prompt, the model, the redaction seam, the gates and the push.

## Not covered

- A conflict inside `scripts/rebase_bot.sh` or `scripts/ci_images.py` would still stop the run
  before the agent; the snapshot only guarantees the Makefile (the common case) and its recipes.
