# check-pr-closing in the unit job reads the PR body live (#1711)

The `linux / unit` job (reusable `pipeline.yml`) runs `make ci-unit`, whose `check-pr-closing` gate
needs the PR body to confirm the adjacent `closes #NN` in both the squash text and the body. It read
that body from the run's **event snapshot** — `PR_BODY: ${{ github.event.pull_request.body || '' }}`
written to `/tmp/pr-body.md` at step start — while the guard and scope jobs had been moved to a
**live** read in #1589. A body-only fix therefore never cleared the unit job's `check-pr-closing`
until a new head SHA was force-pushed to renew the snapshot (measured during #1705: CI run
41891557061 and its reruns 126772833340/126796644190 red on a body that `gh api
repos/<owner>/repos/pulls` showed as correct).

## The fix

`pipeline.yml`'s `make ci-unit` step now reads the body live, mirroring the #1589 pattern used by
`ci.yml`'s guard and `scope.yml`:

- the `PR_BODY: ${{ ... }}` event-snapshot env is removed;
- the step sets `PR_NUMBER`, `PR_REPO`, `GH_TOKEN` and in the run block does
  `PR_BODY="$(gh api "repos/$PR_REPO/pulls/$PR_NUMBER" --jq '.body // ""' 2>/dev/null || true)"`
  before writing `/tmp/pr-body.md` and calling `make ci-unit`;
- a push to `main` has no PR number, so `PR_BODY` stays empty and only the squash half runs
  (unchanged).

A body-only edit now clears the unit job's `check-pr-closing` on `gh run rerun` without a crafted
push — the same rule #1589 established for the guard.

## Prove-the-guard

`tests/test_check_pr_closing.py::test_the_unit_job_reads_the_body_live_not_from_the_event_snapshot`
has the unit step's run block contain the live `gh api repos/$PR_REPO/pulls/$PR_NUMBER --jq
'.body // ""'` read and the whole `pipeline.yml` be free of `github.event.pull_request.body`. With
the defect planted (the event-snapshot form restored) the test FAILS; with the fix it passes.
`check-pr-closing` itself is byte-identical (`scripts/check_pr_closing.py` and the Makefile recipe
untouched), so the adjacency and body-set-equals-commit-set rules are not weakened. Implements
#1711.
