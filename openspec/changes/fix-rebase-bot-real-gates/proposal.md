# fix-rebase-bot-real-gates

## Why

`scripts/rebase_bot.sh` verifies a rebased branch with three gates and treats a failure as
"do not push". Measured in run `39553726935`:

```
docker: Error response from daemon: pull access denied for llgenie/test ...
make[1]: *** [Makefile:1179: lint] Error 125
[rebase-bot] git push --force-with-lease fork HEAD:...
```

Two defects in one line: the gates were a `;` list, so the shell reported only the LAST command's
status and a failing `make lint` was swallowed; and the runner never has the test image `lint`
runs in, so that gate could not pass there at all. The comment claiming "the structural checks
pass on the result" was therefore false.

Issue: [#455](https://github.com/asimov-agent/llgenie/issues/455).

## What Changes

- `scripts/rebase_bot.sh`: the default gates are chained with `&&`, so every one of them must
  pass before the push (a `;` list reports only the last status).
- `.github/workflows/rebase-bot.yml`: provide the pinned test image (`make test-image`) before the
  drain step, so `make lint` can actually run on the runner.
- Tests: a failing gate blocks the push (real actor, real scratch repo); the default chain is
  `&&`; the workflow provides the image before the gate runs.

## Impact

- Affected specs: `rebase-bot-sweep` (modified).
- Affected code: `scripts/rebase_bot.sh`, `.github/workflows/rebase-bot.yml`,
  `tests/test_rebase_bot_sweep.py`, README, `agent-wiki/`.

## Not covered

- `make lint` still runs in the test image by design; the workflow now provides it instead of
  skipping the gate.
