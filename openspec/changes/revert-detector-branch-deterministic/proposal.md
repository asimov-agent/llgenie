# Proposal: revert-detector-branch-deterministic (#2497)

## Why

`tests/test_rebase_lane_scripts.py::test_the_revert_detector_catches_a_revert_and_clears_a_restored_tree`
fails on hosts whose `git init` defaults to `main` (measured 2026-11-11 at `ac0cd6736` on this
host; re-measured at `origin/main` tip): the harness `test-revert-detector.sh` runs `git init -q .`
(inheriting the host default) but later checks out the bare pathspec `master` four times — on a
modern-git host those checkouts answer `error: pathspec 'master' did not match any file(s)` and the
harness exits 1. CI was green only because runners' git defaults still init `master`, so every
lane's local `make test-unit` reddens on this host — indistinguishable from a real defect in the
safety-critical `-X theirs` revert detector.

## What Changes

The harness names its own initial branch: `case_repo` creates each throwaway repo with
`git init -q -b main .` and sets `BASE_BRANCH=main`; all four base checkouts become
`git checkout -q "$BASE_BRANCH"`. No bare/default-dependent branch name remains in the tested
harness; the tested cases and their exit-status assertions are otherwise untouched, so the
negative control (a real `-X theirs` revert must red the detector) is unchanged.

## Acceptance mapping (#2497)

- AC1: the named test passes at the fix on a host whose git init defaults to `main` (this host).
- AC2: `grep master` over the harness is empty; the base pathspec is the harness-created `$BASE_BRANCH`.
- AC3: CI `test-unit` stays green on the implementing PR; the harness's own case-2 revert control
  still reds (asserted by the harness's exit-status checks).

## Not covered / Out of scope

- Other agent scripts with host-default-dependent branch names — none found in
  `agents/llgenie-pr-merge-conflict/skills/llgenie-pr-rebase/scripts/` (grep measured: 0 other
  `master` hits); nothing further to file.
