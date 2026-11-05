# Verification-clone artefacts: false reds that are not your branch

Standalone `git clone` + container verification is how gates are run without a
linked-worktree mount. Several "cluster of FAILED tests" symptoms are ARTEFACTS of the
clone/container, never a defect in the branch. Recognise each by its tell before chasing code.

## A linked worktree inside a container fails every git-dependent test
A linked worktree's `.git` is a FILE pointing at an absolute path that does not resolve
inside the container mount, so `git` calls inside the job fail and tests fail en masse
(a whole suite looks like "37 failed"); on a standalone clone of the SAME sha those tests
pass. If a large, cluster-shaped failure appears in a worktree-mounted run, re-run ONE
failing case on a fresh `git clone` before believing it — the branch is usually fine.

## Root-owned artefacts block re-clone
A clone you ran gates in under `docker run -u root` acquires root-owned artefacts
(`.pytest_cache`, pyc) that block `rm -rf` with `Permission denied`, so a re-clone aborts
`destination path already exists`. Clear with `sudo rm -rf <clone>` — but run that `sudo`
from the interactive `terminal` tool, NOT inside `execute_code` (a non-interactive shell
has no tty and `sudo` aborts `a terminal is required to read the password`). The cheaper
path is to clone into a NEW path (`/tmp/w<n>verify2`) instead of fighting the root-owned
one. Tell a clone was never created: `git log` is empty and its `Makefile` is missing yet
the clone command "succeeded".

## A bind-mounted clone is a LIVE view — never `rm -rf` while its `docker run -v "$PWD":/repo` runs
Deleting the host dir under a running container rips the filesystem view out mid-iteration:
the gate emits a cluster of `FAILED` tests a clean run on the same sha never shows —
a corrupted-view symptom, NOT a real red.

**The cluster's tell is not POSITION, it is MODULE KIND:** failures land in the
git/worktree/workflow/wiring modules (`test_worktree_report`, `test_worktree_prune`,
`test_workflows_valid`, `test_workflow_guards`, `test_wiring`), all absent from your diff, and
they can be a TAIL cluster (`test_w*`) rather than an early `FFFFF` one — do not wait for
"a cluster BEFORE the touched modules", or a 50-failure tail red reads as genuine ambient.

**Deletion guard:** a scratch clone may be deleted ONLY when (a) its gate log already contains
`EXIT=`, AND (b) no process/container is still attached (`docker ps`, or
`ps -eo pid,etime,cmd | grep -iE 'unit_tests|docker run' | grep -v grep` shows nothing).
Doing cleanup CONCURRENTLY with other wrap-up steps is how this breaks — the gate runs 10+ min
in the background while you tidy and the `rm` lands mid-run. Treat scratch-clone cleanup as the
FINISH step, after the background gate's completion notification. On seeing such a cluster,
kill the run, re-clone to a fresh path, re-run clean before believing the red — own it as your
artefact, not the branch's.

## A `--depth 1 --single-branch` clone lacks `origin/main`
That missing ref reds `ci-scope`/`check-docs` spuriously and reds UNIT tests that resolve
`origin/main` (an order/publish test diffing against the base) — a CLONE ARTEFACT, not your
regression. Discriminator: the test passes at your branch head AND at a clean `origin/main`
checkout and fails ONLY inside the single-branch clone. Confirm by running the exact test at
both shas (`pytest tests/test_<x>.py`); a live CI run (which resolves `origin/main`) is the
tie-breaker. Fetch main into the clone or do a full clone; never "fix" the artefact in code.

## A verification clone's `origin` is the FORK — its `base..HEAD` diff is a fork-main artefact
`git clone <fork-url>` sets `origin` to the fork (`andyholst/llgenie`), not upstream
`asimov-agent/llgenie`. The fork's `main` has diverged from upstream (extra commits, a different
tip), so `git merge-base origin/main HEAD` and `git diff origin/main..HEAD` computed in that clone
resolve against the FORK's main: they name files that are NOT in your PR (another lane's merged
refs, a `SOUL.md`) and a merge-base that predates your real base. That diff is a fork-main
artefact, not your change set. Run the authoritative base range in the WORKTREE against upstream
`refs/remotes/origin/main` (explicitly fetched), or re-point the clone's `origin` at upstream.
Use the clone only for tree-CONTENT gates (`make lint`, `make check-docs`); never to compute the
base range or the PR's file list. (`--depth 1` also leaves `origin/main` missing entirely — see
above — so deepen before any ancestry check.)

## `gh` from a standalone verification clone reads the WRONG repo
Its `origin` is the local checkout, not GitHub, so `gh pr view`/`gh pr comment` query nothing
useful (or a repo with no such PR). Always pass `--repo asimov-agent/llgenie` explicitly, or
run `gh` from the canonical GitHub-backed worktree. The clone exists for the gates; it is not a
`gh` context — and pushing from it goes to the LOCAL repo, so push from the worktree.
