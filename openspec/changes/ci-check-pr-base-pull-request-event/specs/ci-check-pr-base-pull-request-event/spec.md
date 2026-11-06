# Spec: ci-check-pr-base-pull-request-event

## Behavior

1. `make check-pr-base` in `.github/workflows/ci.yml` runs only when the triggering event is
   `pull_request`; on a `push` (including a push to `main`) the step is skipped.
2. On a `pull_request` run the gate is unchanged: it re-fetches the base's live `main` and
   fails iff `git merge-base <base> <head> != <base>` (the #845 foreign-commit protection).
3. The workflow comment states the skip-on-push scope and does not claim a push is a tautology
   while the gate still refers a moving `origin/main`.

## Non-goals

- `scripts/check_pr_base.py` logic is unchanged; a pull_request still reds a branch cut from
  another PR.
- The #845 negative control (a one-commit-ahead clean branch) still passes.
