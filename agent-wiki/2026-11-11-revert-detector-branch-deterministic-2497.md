# Revert-detector harness names its own base branch (issue #2497)

## What changed

`test-revert-detector.sh` (the negative control for the `-X theirs` silent-revert detector in
`post-rebase-verify.sh`) built its throwaway repos with `git init -q .` and then checked out the
bare pathspec `master` four times. On a host whose `init.defaultBranch` is `main` (this host;
git 2.47-era default) every one of those checkouts answered `error: pathspec 'master' did not
match any file(s)` and the harness exited 1 — so `make test-unit` reddened locally while CI was
green only because runners still init `master`. A red local gate for one of the lane's most
safety-critical detectors was indistinguishable from a real detector defect.

The fix makes the harness self-contained: `case_repo` now runs `git init -q -b main .` and sets
`BASE_BRANCH=main`; the four base checkouts became `git checkout -q "$BASE_BRANCH"`. Case logic
and the exit-status assertions (including the `-X theirs` revert control that must red) are
untouched.

## Verification

- This host (`git config init.defaultBranch` → `main`): named test `1 passed`, rc=0; full module
  26 passed; harness direct run PASS, rc=0.
- Old-shape control: the pre-fix harness copy run on the same host reproduces the exact failure —
  rc=1 with four `pathspec 'master' did not match` errors — proving the fix is what flips it.
- `grep master` over the scripts dir: only the fixed harness's `$BASE_BRANCH` form remains (0
  bare hits).

## Current status

Branch `feat/2497-revert-detector-branch` -> PR against upstream main carrying `closes #2497`
in both commit text and body (check-pr-closing gate); CI `test-unit` proves the both-shapes
claim on the PR.
