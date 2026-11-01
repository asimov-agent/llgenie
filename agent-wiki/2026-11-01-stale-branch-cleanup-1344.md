# Cleanup pipeline: delete stale non-`main` branches (issue #1344)

The repo accumulates non-`main` remote branches with no retirement mechanism (measured: 48 at
`origin/main@793ac1dc`). This pipeline clears branches that are **at least 3 days old AND fully
delivered**, exactly once a day (03:39 UTC — an odd minute owned by no existing workflow) plus manual
dispatch; **deletion only via `APPLY=true`**, so the cron never silently deletes.

The dangerous part is that most non-`main` branches are **squash-merged PR branches** — their tip is
NOT an ancestor of `main` (the #1317 lesson) — or unmerged bot/verification branches, so a naive
age-ancestry sweep would destroy in-flight and already-delivered-squash work. The deletion predicate
is therefore gated on a live-vehicle check, never on age alone. A branch is deleted ONLY when **both**
hold:

- no open PR names that head ref (`gh pr list --head <branch> --state open`), AND
- every commit on it is already in `origin/main` **or its PR is MERGED/CLOSED** — use the compare
  endpoint (`behind`/`identical`) OR the PR state, so a squash-merged branch (tip never an ancestor)
  is still recognised as delivered.

A branch with an open PR, or with commits `origin/main` lacks and no merged/closed PR, is **reported,
never deleted**. `main`/`master`/any protected branch is never touched. Each deletion logs branch, tip
sha, age and the evidence.

- workflow: `.github/workflows/stale-branch-cleanup.yml` — schedule `"39 3 * * *"` + `workflow_dispatch`
  (`APPLY`, default `false` = report-only), byte-identical actor guard (owner / repository bot /
  collaborator with write), static concurrency with `cancel-in-progress: false`.
- gate: `scripts/stale_branch_cleanup.py` + `make stale-branch-cleanup` (APPLY=1 deletes,
  AGE_DAYS= overrides). Watched by the run-failure-reactor roster.
