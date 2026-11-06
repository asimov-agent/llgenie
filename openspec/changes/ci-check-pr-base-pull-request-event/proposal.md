# Fix: gate `check-pr-base` to the pull_request event in ci.yml

## Why

On a `push` to `main`, the `make check-pr-base` step in `.github/workflows/ci.yml` ran and
re-fetched `origin/main` live. The pushed commit IS main's history the instant the run starts,
but in a busy fleet `origin/main` had already advanced by the time the gate fetched — so
`git merge-base origin/main HEAD == HEAD != origin/main` and the gate red on a phantom
base-staleness (`foreign commits (0)`, content IS on main; measured runs `42209323920` @
`d7f5b33329` and `42209857316` @ `7b2c9e5d57`). The #845 protection exists to catch a PR
branch cut from another PR, which a push event cannot be.

## What changes

The step now carries `if: github.event_name == 'pull_request'`: it is skipped on a push (no
meaning, no phantom red) and runs the unchanged live-fetch merge-base-equals-base test on a
pull request (`scripts/check_pr_base.py` untouched). The workflow comment now states the real
event scope instead of the false "push is a tautology" claim.

## Who

llgenie-ci-pipelines-maintainer (this lane owns the gate-defect PR; issue #1867).
