# `ci-verdict` paginates the `main` run listing so the truncation guard stays a real guard (issue #1617)

`scripts/ci_verdict.py` exists to hold a finished CI run to its scope decision (#1111): a selected
job that is skipped/cancelled/absent, or a run with no decision, is a FAILED verdict, and the
`ci-verdict` check-run on the head carries it. To decide whether a cancelled run has been
superseded by a later run of the same workflow on the same branch, `superseding_run` lists the
branch's runs via the GitHub `…/actions/runs?branch=…` endpoint and its logic uses `total_count`
to make sure it did not miss anything.

The #1582/#1610 truncation guard — `total_count > len(runs) → raise` — is a real guard: a verdict
reached from a truncated listing can be a false one, so a run that cannot prove its newest
superseder must not post a false `failure`. That guard is correct, and it stays. What changed is
what the guard has to look at.

A busy branch like `main` now exceeds one page of the run listing. Measured 2026-11-02: `main`
reports **2500+ runs** with a single page of 50 rows. The guard then rightly says "one page
returned 50 — that cannot be a verdict" — but the fetch was asking for only one page, so the red
was not a real truncation, it was the workflow not having walked far enough. The same head flipped
between success and failure run to run (the verdict was only reachable when the fetched page
happened to satisfy the guard), and that flakiness stops as run volume grows — deterministic,
not infra.

The fix paginates the fetch instead of resolving to a single page:

- a new `branch_runs(repo, branch)` walks `…/actions/runs?branch=…&per_page=100&page=N` through
  every page, deduping by run id (a retried/stale page does not double-count), collecting rows
  until `total_count` is satisfied or a page adds nothing;
- the #1582/#1610 guard now binds only on a **genuine** shortfall — pages whose union still falls
  below the reported `total_count` (an exhausted listing that cannot prove its newest superseder)
  still raises the exact `truncated listing cannot be a verdict` error;
- no gate, forbid policy, or severity is weakened; the workflow YAML is untouched — the change is
  entirely in `scripts/ci_verdict.py` and its tests.

Regression tests prove both directions (#1617 acceptance #4): a healthy multi-page listing (150
runs across pages of a `per_page=100` walk) is fully walked and still finds the superseder, and a
listing whose pages together fall 100 rows short of a reported 150 still refuses with the
truncated-listing error. `make ci-unit` carries the change.

Delivered as a reviewable PR on branch `fix/1617-ci-verdict-pagination` (base `origin/main@05ac0f05`),
ready for the #1088 owner gate.
