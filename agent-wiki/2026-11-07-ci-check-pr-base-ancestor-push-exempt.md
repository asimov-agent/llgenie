# `check-pr-base` exempts an ancestor-of-live-main head (push-to-main race) (#1867, #1906..#1909)

On a push-to-`main` CI run, `make check-pr-base` red on a phantom base-staleness whenever
`main` advanced between the run's HEAD and the gate's live `git fetch origin main`. The
gate's protection (issue #845) exists to catch a PR branch cut from another PR carrying that
PR's diff; on a push the pushed commit IS main's history, so `base..rev` is empty and there
is nothing foreign to leak.

Issue #1867's fix (PR #1874) event-gated only the `make check-pr-base` **step in the ci.yml
guard job** (`if: github.event_name == 'pull_request'`) — but `linux/unit` runs `make ci-unit`,
and `ci-unit` calls `$(MAKE) check-pr-base` UNCONDITIONALLY in the Makefile, so a push-to-main
run that reds `check-pr-base` still reds `linux / unit` (run `42330618401` @ `9679157e`,
`make: [Makefile:1114: check-pr-base] Error 1`). The #1867 guard therefore did not close the
loop.

Fix: `scripts/check_pr_base.py::check` now PASSES when `base..rev` is empty — the exact
condition where the #845 leak cannot apply. Because the exemption lives in the gate's own
semantics it covers every caller (the ci.yml guard-job step AND `linux/unit`), whereas the
#1867 event-scope guard covered only one invocation. The PR-race guard is unchanged: a branch
cut from another PR always has a non-empty `base..rev` and still fails, and a clean
one-commit-ahead branch still has `merge-base == base` and passes. Evidence (before/after):
runs `42330525270` @ `c3dc135f` (#1804) and `42330618401` @ `9679157e` (#1896), both RED with
foreign commits (0); the reproduced shape is GREEN after the fix.
