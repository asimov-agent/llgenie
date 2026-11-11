# Running `make loop` in the background

When you background the loop to keep working, the wrapper's own exit code is
meaningless — `(make loop > log 2>&1; echo "LOOP_EXIT=$?" >> log)` returns the
`echo`'s rc (always 0), so the real verdict is the `LOOP_EXIT=` line in the log,
never the process exit code. Read that line before claiming green.

A loop that started before an edit landed is testing a MIXED tree: stages that
already collected run the old code, later stages the new. A mid-run edit can
turn a would-be-green run red (or hide a real failure) and the log gives no
signal. Freeze the commit first (commit the fixes, note the sha), start the
loop on that exact sha, and if you must edit mid-run, kill the loop and restart
on the frozen commit — never trust a run that overlapped an edit. A
killed/superseded run's exit code says nothing about the tree; only the run on
the frozen commit is authoritative.

## Reading the verdict

```bash
# start (background):
(make loop > /tmp/loop.log 2>&1; echo "LOOP_EXIT=$?" >> /tmp/loop.log) &
# later — the process exit code is the echo's (0); the real answer is in the log:
grep LOOP_EXIT /tmp/loop.log
```

## Freezing the tree

```bash
git commit -am "fix: ..." && git rev-parse --short HEAD   # note the sha
# start the loop on that exact sha; do not edit until it finishes
```

If a stage fails, fix and re-commit, then restart the loop on the NEW frozen sha
rather than resuming — a run that overlapped an edit is not evidence.
