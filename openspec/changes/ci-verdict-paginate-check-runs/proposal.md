# ci-verdict reads every check-run on a busy head — a 100-row page is not a refusal

## Why

`scripts/ci_verdict.py::check_runs_of` (added with #2116) reads the head's check-runs as **one page of
100** and refuses anything larger as "truncated". A busy `main` head exceeds that. Measured 2026-11-08
on CI run `42452592982` (`push`, head `520db900`, branch `main`): the head reported **192** check-runs,
one page returned 100, so the verdict exited 2 with `head 520db900... reports 192 check-run(s) and one
page returned 100: a truncated listing cannot be a verdict` — no `--check-run-out` payload was written,
the workflow's "Post the verdict" step died on `no check-run payload: the verdict step did not reach a
verdict`, and the head carried **no** `ci-verdict` row. Every re-judge of the class failed the same way
and the run-failure reactor filed a new issue per re-judge (#2115 #2120 #2133 #2150 #2153 #2154,
collapsed into #2156).

## What changes

1. `check_runs_of` walks the pages of `/repos/{owner}/{repo}/commits/{head}/check-runs?filter=latest`
   exactly like `branch_runs` walks a busy branch's `/actions/runs` listing (issue #1617): page 1 keeps
   its original URL shape (no `&page=` — GitHub treats a bare listing as page 1), later pages append
   `&page=N`, rows are deduped by id, and the #1582/#1610 truncation guard binds **only on a genuine
   shortfall** — the pages read still fall short of `total_count`, or a page ends early and the next
   adds nothing.
2. An **empty** listing (`total_count == 0`, the shape every #2116 fixture answers) is a clean `[]`,
   never a false refusal.
3. The unreachable-verdict path is unchanged: exit 2 with **no** check-run — the settle-gate and
   unreadable-artifact tests assert that a genuinely unreachable verdict must not post a possibly-wrong
   verdict; the reactor still files the issue.

## Change-first

GitHub issue #2156 is the single surviving tracker this implements; the branch
`fix/2156-verdict-paginate-no-verdict` carries the change; the PR closes #2156.
