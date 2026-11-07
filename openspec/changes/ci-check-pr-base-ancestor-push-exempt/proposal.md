# Fix: exempt a check-pr-base head that is an ancestor of live main (push-to-main race)

## Why

`check-pr-base` reds a LEGITIMATE main merge on the push path when two merges land
back-to-back. On a push to `main`, the gate re-fetches `origin/main` LIVE, and a busy
fleet has already advanced it past the pushed commit by the time the check runs — so
`git merge-base origin/main HEAD == HEAD != origin/main` and the gate reds on a phantom
base-staleness (`foreign commits (0)`, the pushed content IS on main; measured runs
`42330525270` @ `c3dc135f` (#1804) and `42330618401` @ `9679157e` (#1896)). The reactor
auto-filed four identical issues for the same landscape: #1906, #1907, #1908, #1909.

Issue #1867's fix (PR #1874) event-gated only the `make check-pr-base` **step in the
ci.yml guard job** (`if: github.event_name == 'pull_request'`). That did not close the
loop: `linux / unit` runs `make ci-unit`, and `ci-unit` in the Makefile calls
`$(MAKE) check-pr-base` UNCONDITIONALLY — so a push-to-main run that reds `check-pr-base`
still reds `linux / unit` (run `42330618401` is exactly that, `failure` on `linux / unit`
with `make: [Makefile:1114: check-pr-base] Error 1`).

## What changes

`scripts/check_pr_base.py::check` passes when `base..rev` is empty — the head is an
ANCESTOR of the live base, so the #845 "branch cut from another PR leaks that diff" concern
cannot apply (there is no diff absent from the base to leak). This is the precise condition:
the PR-race guard remains intact because a branch cut from another PR ALWAYS carries foreign
commits (`base..rev` non-empty), and a clean one-commit-ahead PR branch still has
`merge-base == base`. Unlike the #1867 event-scope guard (which only ever covered the
ci.yml guard-job step), this fixes EVERY caller — the ci.yml guard job step AND
`linux / unit` via `make ci-unit` — because it changes the gate's own semantics, not one of
its invocations.

The `#1867` ci.yml `if:` guard stays (harmless belt-and-suspenders, tested by
`test_the_check_pr_base_step_is_gated_to_pull_request`); the script-level exemption is the
real correction.

## Who

llgenie-ci-pipelines-maintainer (this lane owns the gate-defect PR; issues #1906..#1909).
