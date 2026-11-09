# Resuming a revived PR branch, and reds that are not yours

## The local tip is often a pre-rebase duplicate

A lane revived after a crash usually finds its PR already open, and `HEAD` in the old worktree is
**not** the PR head: rebase-bot has since replayed the same commit onto a newer `main`, so the local
branch holds an identical-tree duplicate on the old base. Check before you do anything.

1. `git remote -v` — the fork is `fork` (`andyholst/llgenie`), the canonical upstream is `origin`
   (`asimov-agent/llgenie`). `git fetch fork` then read `fork/<branch>`; if the branch is never
   fetched, `origin/<branch>` looks like it does not exist and you conclude the PR is gone.
2. Compare CONTENT, not shas: `git diff --stat HEAD fork/<branch>` and confirm none of your own
   files appear in it (what is left is only `main`'s newer commits). Compare the two commits'
   diffstats too — identical counts over the same file list means the same change.
3. Only then `git reset --hard fork/<branch>`; never push the pre-rebase duplicate (it rewrites the
   rebase lane's work and drops newer `main`).
4. Verify against the remote tip, not the old local tree: `make test-unit`, `make check-docs`,
   `make openspec-validate NAME=<change>`, `make lane-preflight`.
5. Check no run is in flight at the head before pushing: `gh run list --branch <branch>` and require
   every row `status: completed`.

## A red `check-pr-acceptance` on a PR that closes its own issue is usually NOT yours

`make check-pr-acceptance` reads the ISSUE's `## Acceptance criteria`. A criterion like "the PR that
fixes it is green in CI on the same job that failed" cannot be true before the PR is green, so the
gate reds until a verdict-gated write-back ticks it. That write-back belongs to the reviewer lane,
not the implementer: read the job log, quote the violation, and say so. Do not hand-tick the issue
and do not race the reviewer — a second writer on the issue body is a conflict.

Corollary when reading a PR's checks: `guard` and `scope` both run this gate, so ONE cause reds two
jobs, and `ci-verdict` then reds *correctly* downstream (`guard FAILED`, siblings skipped, `NO
DECISION`) — three red check names, one cause. Quote the log line, not the badge, and say which
lane owns the write-back.

## Guard-prove inside the test image

`make test-unit` runs pytest in `llgenie/test:latest`; for a single file use the same image so the
tree is the tree CI judges:

```bash
docker run --rm -u root -v "$PWD":/repo:rw -w /repo -e HOME=/root llgenie/test:latest \
  python -m pytest tests/test_<x>.py -q -p no:cacheprovider
```

Then plant the bug (revert the predicate), run the new test — it must FAIL naming the old behaviour
(`assert 1 == 2`) — restore, and count zero. Restore from a copy taken BEFORE the edit; a `git
stash pop` after `reset --hard` loses the fix.
