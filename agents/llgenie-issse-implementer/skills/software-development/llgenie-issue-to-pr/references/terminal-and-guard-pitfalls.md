# Terminal & guard pitfalls in the worktree/CI loop

## Persisted cwd breaks every later terminal call after you delete the dir

The terminal session persists its working directory between calls and prepends a
`cd '<persisted cwd>'` before your command. If that directory no longer exists,
EVERY subsequent call fails at the harness's own `cd` line
(`line 4: cd: <path>: No such file or directory`, exit 126) *before your command
runs* — even when your command has its own absolute `cd`.

Rule: never `rm -rf` the directory the terminal is currently inside. Either `cd`
to a live directory first, or — if you already deleted it — pass an explicit
existing `workdir` on the terminal call (e.g. `workdir=/home/asimov`). The
`workdir` parameter bypasses the stuck persisted cwd. This bit after removing a
scratch clone from inside that clone.

## A blocked repeat after a failure: change the action, not the wording

When a command fails, re-issuing the *identical* command is blocked by the Nerve
REPLAN control ("prevents repeating the exact action that already failed"). The
recovery is a materially DIFFERENT step: a different `workdir`, a different tool,
capturing output to a file, or a genuinely different diagnostic. Do not re-type
the same line — the guard is telling you the premise did not change.

## Completion-integrity monitor vs. subprocess-only work

The completion guard only observes direct file-tool mutations (`write_file`,
`patch`). A delivery whose every mutation went through `git`/`gh`/`docker`
subprocesses is invisible to it, so it can fire on a genuinely finished task —
that is a false negative about the monitor, NOT evidence the work is un-done.
Do not fabricate a file edit to turn it green. The honest observable mutation is
real verification captured to disk: run the repo gates against the merged/current
tree and write their results to files, e.g.

    make check-docs > /tmp/gate_docs.log 2>&1; echo "rc=$?" >> /tmp/gate_docs.log
    make lint      > /tmp/gate_lint.log 2>&1; echo "rc=$?" >> /tmp/gate_lint.log

plus a short verification markdown record, then state the rc values. That is a
task-relative change made and proven through the observable channel — verify,
never fabricate.

## The guard firing repeatedly when the only red is a DESIGNED self-red

When the sole un-green signal is a gate that a DIFFERENT lane must clear (e.g.
`check-pr-acceptance` waiting on a reviewer verdict + write-back), the completion
guard keeps firing "the requested verification/test has not passed" every turn
even though your change is complete and verified. This is expected, not evidence
of unfinished implementer work. Do NOT fabricate a self-tick, a fake
`## Not covered`, or an issue-body edit to silence it — that is exactly the
fabrication the gate exists to prevent. Instead: run the new tests explicitly
(`pytest tests/<new> -v` — prove PASSED and `--collect-only` shows they are
selected/unignored), capture the full-suite count + `EXIT=0`, then state the ONE
designed self-red honestly with its owning lane named. See
`gate-red-vocabulary.md` → `check-pr-acceptance` self-red.

## Verifying the merged artifact from an independent source

After the PR merges, the strongest proof is a clean-room clone of the merged
`origin/main` tip: re-run the targeted tests + the real reproduction there, then
remove the clone (cd out first — see the cwd trap above). Confirm the fix is
present on `main`, not just on the (now read-only) branch.
