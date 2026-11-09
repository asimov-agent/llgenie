# Shared worktrees get repurposed by other lanes

Lanes run concurrently on one host and reuse `/tmp/wts-*` paths. A worktree that held your
union an hour ago can be at a different HEAD now, with another lane's commit checked out.

**Rule: never trust a worktree path — re-measure it or rebuild fresh.**

Before publishing any sha that came out of a worktree, re-derive it from the tree itself:

```bash
cd <wt> && git rev-parse HEAD && git status --porcelain | wc -l
```

If the HEAD is not the commit you built, or porcelain is non-empty, the worktree has been
repurposed: build the union in a *new* directory (`/tmp/wts<pr><suffix>`) instead of
reusing the old one. Naming a second, distinct suffix per attempt (e.g. `wts1696re` after
`wts-1696b3`) keeps attempts separable and makes the repurposing obvious.

Consequences when this is skipped: a "verified" sha that exists only in the old worktree's
reflog, a report describing files that are no longer there, and a push of the wrong tree.

## Local-only unions still need the full gate

A union that will not be pushed yet (owner hold, never-kill run at head) is still a claim
about a tree, so gate it at the exact anchor and quote the anchor in the result line:

```bash
timeout 1500 docker run --rm -u root -v <wt>:/repo:rw -w /repo -e HOME=/root \
  llgenie/test:latest python scripts/unit_tests.py run
```

- Use `scripts/unit_tests.py run` (the canonical runner), not bare `pytest` on guessed paths —
  guessed test paths match nothing and the gate "passes" with zero tests run.
- Print `git rev-parse HEAD` and `git status --porcelain | wc -l` *inside* the same script so the
  anchor sha is attached to the pass count in one line of output.

## Re-cutting onto a moved base

When the base advances by one merge after you built the union, re-cut rather than rebasing the
union commit (the rebase re-resolves conflicts you already resolved). Build from fresh
`origin/main` and re-apply the PR's own diff, then confirm three things before reporting:
`parent == live main`, `check-pr-base` rc=0, and the union's blobs identical to the canonical
lineage for the files it extends.
