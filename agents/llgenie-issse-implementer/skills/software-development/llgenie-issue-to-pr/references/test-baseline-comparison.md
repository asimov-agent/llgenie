# Test baselines: proving a change did not regress

## Use the repo's own target, never ad-hoc `docker run` + pytest

`make test-unit` selects files through `scripts/unit_tests.py`; a hand-rolled
`docker run … pytest tests/` selects a different set and surfaces dozens of
spurious `E`/`F` markers that do not exist in CI. The invocation that matches CI
is the make target, run from a real worktree.

Consequence: a cell that runs the full suite hits the ~300 s tool cap. Start it
with `terminal(background=true, notify=true)` writing to a log and read the log
tail; do not loop short polls (each 300 s cell that times out loses the run).

## Git-from-worktree failures inside the container are harness artifacts

When tests shell out to git from a container mounted on a worktree, they can die
with:

```
fatal: not a git repository: <repo>/.git/worktrees/<name>
```

The container sees a worktree pointer, not a repository — a harness artifact,
not a defect in the change. Symptoms look like an unrelated suite (e.g. a bump/
plan module) suddenly failing 20+ tests only on your branch.

## Deciding "did my change regress this?" — the git-less baseline

Do not compare against a worktree. Compare against a copy in a plain directory
with no `.git` at all:

1. Extract pristine `origin/main` into a fresh dir (no repo metadata).
2. Run the suspect suite there → baseline pass/fail counts.
3. Overlay your changed files onto another pristine copy (still no `.git`) and
   run the same suite → if the counts match the baseline, your change caused no
   regression; if they differ, it did.

Record both numbers. "N failed on mine vs 1 pre-existing on pristine" without
the identical invocation and the same network conditions is not a finding.

## A committed-vs-working-tree diff test reds on a DIRTY tree, not a regression

Some gate tests compare the COMMITTED file (`git show <ref>:path`) against the WORKING-TREE file
(`(REPO/path).read_text()`), e.g. a "params identical to base are not deferred" check. Any
uncommitted edit to a tracked file makes such a test red locally, while CI — a clean checkout —
passes and the same test passes on the committed head. Before diagnosing a full-suite red as a
regression, run `git status --short`; commit or stash the tree and re-run the suspect test, then
confirm once more on the committed head. Do not chase a source fix that the test only sees because
your tree was dirty.

## Container hygiene when several lanes test at once

- Identify your containers by their mount path before touching any.
- Kill only your own by container id; never `pkill -f pytest`/`docker` by name —
  it can SIGTERM your own shell and it reaches other lanes' runs.
- A container mounted on another lane's worktree is that lane's artifact: leave
  it and report it.
