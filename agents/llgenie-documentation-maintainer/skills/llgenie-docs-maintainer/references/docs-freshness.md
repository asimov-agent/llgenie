# Docs freshness — the lane owns README + docs against the tree

Versioned via #1239 (owner directive, 2026-10-31). Applies to the documentation-maintainer lane.

## Remit

The lane owns README.md, `docs/` and every user-facing doc/manpage make target. Whenever a
code/scripts/workflow change lands on `main`, the doc that describes it is re-checked and updated in
the SAME pass as the change, never later. The `make check-docs` gate (Makefile:987) enforces that
every user-facing target is documented — it is the lane's gate, kept green on `main`.

## 30-minute change monitor

On a recurring ~30-min cadence the lane reads `main` for new commits/merges and, before filing or
taking up any other work, answers: **"does any user-facing doc/README need an update for this
merge?"** A merge that is already doc-current (check-docs green at its head, description accurate)
is answered "no gap" and recorded; a merge with a documented-but-description-lagged change is fixed
in the same pass (rebase the doc PR onto the merge, update the description, re-run the gate). Measured
freshness, not passive: a census of what was checked and at which sha is the unit of work.

Checklist, per merge:
1. `git log origin/main -1` — what merged, which heads touched scripts/`.py`/workflows/`.yml`/Makefile.
2. Does any user-facing doc name that target / script / behaviour? (`grep -R <target> README.md docs/`)
3. Is the description still truthful at the new head? (`make check-docs` exit 0; re-read the sentence)
4. Gap → fix the doc in the same pass; no gap → record "checked <sha>, no gap" and move on.

## When the monitor finds a RED gate on `main`

A merge whose gate is red on a **pure `origin/main`** tree is a repo-wide blocker, not your diff's
problem: a census pointer that no longer resolves reds `check-docs` on every branch and blocks the
`scope` job of every open PR. Notice it before the fleet does, and classify it with one command —
`git cat-file -e <pointer>^{commit}`:

- exits non-zero ("Not a valid object name"): the pointer is a **sha that was never a commit** — a PR
  hand-edited the census line instead of taking the generator's output. This is the usual cause of a
  red `check-docs` on `main`.
- resolves, but `git merge-base --is-ancestor <pointer> HEAD` is false: a **real commit the branch
  does not contain** (a squash-orphaned pointer); a plain refresh fixes it.

Fix shape (docs-only, this lane):
1. File the issue with the measured red — the `[census-gate]` lines from `make -s check-docs` on a
   scratch pure-main worktree, plus the `cat-file` result. A red gate on `main` is an issue with
   numbers, never a chat narrative.
2. Re-point the doc at a real ancestor and set **every** count from the gate's own measure output
   (`python3 scripts/check_architecture_census.py measure <sha>`) — never hand-typed, never a
   hand-picked sha. The gate measures the claim tokens at the doc's pointer, so the pointer and the
   counts must come from the same commit.
3. Prove green in both states the gate sees: `make -s check-docs` on the fix head **and** on a
   merge-tree of the fix onto `origin/main` (`git worktree add /tmp/mt origin/main`, merge, run the
   gate, remove the worktree). Green on the head alone is the weaker measurement.
4. Leave the durable generator fix as its own issue — the re-point is a short-term unblock, not a fix
   for the script that let a fabricated sha reach the doc.

Re-fetch `main` in the moment you cut the fix worktree, and write the base sha into the issue's start
comment; do not fix against a `main` read minutes earlier.

## Never a private profile edit

Any refinement to HOW this lane does documentation (a new checklist, a new gate, a new cadence) is
versioned under `agents/llgenie-documentation-maintainer/` via an issue + PR (issue #791 pattern).
Live is authoritative for drift; a change authored in the tree is mirrored tree→live so
`make sync-agent-profile CHECK=1` stays green. This reference itself is such a versioned refinement.
