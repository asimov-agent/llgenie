# ci.yml gates `check-pr-base` to pull_request (#1867)

On a push-to-`main` CI run, `make check-pr-base` red on a phantom base-staleness whenever
`main` advanced between the run's HEAD and the gate's live `git fetch origin main` — the
merged-head `merge-base` is the HEAD itself, not the re-fetched (already advanced) `origin/main`.
The step ran on every event, yet the gate's protection (issue #845) exists only to catch a PR
branch cut from another PR, which a push event cannot be.

Fix: the step is now event-gated with `if: github.event_name == 'pull_request'`. `push`
runs skip it entirely; `pull_request` runs keep the live-fetch merge-base-equals-base test
unchanged (`scripts/check_pr_base.py` untouched). Evidence: runs `42209323920` @
`d7f5b33329` and `42209857316` @ `7b2c9e5d57`, both foreign commits (0).
