---
name: census-tree-at-sha
about: The architecture census is checked against the tree at the sha it names, not HEAD
status: active
---

# Check the architecture census at the tree it names (issues #1053, #1043)

## Proposal

`scripts/check_architecture_census.py` takes `HEAD` as the ground truth of every claim: `measure()`
counts `git ls-tree -r --name-only HEAD` and the pointer half compares the tracked count at the
named sha against the count at `HEAD`. A census is a fact about **one commit**, so the doc is only
satisfiable when it has been re-derived from the tree the gate happens to see — which means every
open PR that adds a file has to rewrite the same census block in `docs/ARCHITECTURE.md`. That one
shared hunk is the only conflicting path between `main` and several open branches, and the pointer a
PR is forced to write names that PR's own head, which dangles once the PR is squash-merged.

## Motivation

Measured on `main@369e191`: five open PRs are red or `CONFLICTING` on this gate and nothing else —
`#1049` `scope` FAILURE (run 41086848427), `#953` `linux / unit` FAILURE (run 41070995866), `#932`,
`#1050`, and `#932`/`#953` conflict with `main` on `docs/ARCHITECTURE.md` only. The second gap is in
the same function: the pointer is checked for existence (`commit_is_real`) but never for reachability,
so a branch head that is not an ancestor of `HEAD` can satisfy it — the remaining half of #1043.

## Change

- `scripts/check_architecture_census.py`: `measure(ref)` counts the tree at `ref`; `check()` reads the
  doc's `measured at <sha>` pointer and, when the pointer is a real commit that is an ancestor of
  `HEAD`, compares every census claim against the tree **at that sha**. A missing pointer, a dangling
  sha and a non-ancestor sha each red, naming the sha and the reason; a claim that disagrees with the
  tree at the pointer names **both** values.
- `tests/test_architecture_census.py` (new, hermetic scratch git repo): the old script fails three of
  the five fixtures (the file-adding branch, the both-values message, the non-ancestor pointer); the
  new script passes all five.
- `docs/ARCHITECTURE.md`: the structural-gates row states the referent (no census number moves).
- `agent-wiki/` note + `docs/changes.d/` fragment (the index row lives in the fragment).

## Acceptance

- [ ] `python3 scripts/check_architecture_census.py check` exits 0 on a branch that adds files and
  leaves `docs/ARCHITECTURE.md` untouched.
- [ ] A doc number bumped by 1 reds naming both values; restoring it exits 0.
- [ ] A pointer to a real commit that is not an ancestor of `HEAD` reds naming that sha.
- [ ] A missing pointer and a dangling sha still red.
- [ ] `make lint`, `make check-docs`, `make check-wiring`, `make openspec-validate
  NAME=census-tree-at-sha` exit 0.
