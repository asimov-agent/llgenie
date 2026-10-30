---
name: architecture-census-gate
about: Gate the ARCHITECTURE.md census against the tree
status: active
---

# Gate the architecture census (issues #896, #1033)

## Proposal

`docs/ARCHITECTURE.md` states a census of the tree ("The tree is N tracked files: data/ 9, skills/ 17,
... and `docs/` 7.") and two cells with the `tests/test_*.py` and `openspec` change counts. When the
tree changes, nothing checks that the document still agrees. It has drifted at least twice in two days,
each time found by hand. Add a gate that counts the tree with `git ls-tree -r --name-only HEAD` and
fails when the document's claims disagree, naming both values and the sha it measured.

## Motivation

A census is a claim, and claims rot. Nobody owns this one, so the correction waits for a bot to notice —
the same shape as every other unguarded invariant this repo has had to file. The measurement already
exists (`scripts/architecture_bot.py` counts tracked files); the gap is a reproducible check wired into
a gate.

## Change

- New `scripts/check_architecture_census.py` (stdlib only): `check` parses the census sentence and the
  two count cells out of `docs/ARCHITECTURE.md`, counts `HEAD` with `git ls-tree -r --name-only`, and
  exits 1 on any disagreement naming both values; `report` prints the census and always exits 0.
- `Makefile`: new user-facing target `check-architecture-census`, registered in `.PHONY`, run as part
  of `check-docs`, and called directly by the `ci-unit` job (so `check-wiring` sees a CI job reach it).
  Because `ci-unit` runs it, `scripts/issue_bot_gates.py` classifies it in `DEFERRED` with the reason
  that a census change is re-checked on the bot's own PR.
- `docs/ARCHITECTURE.md`: the census updated to the current tree with a `measured at <sha>` note, and
  the new gate named in the structural-gates row.

## Acceptance

- [ ] `make check-architecture-census` exits 0 on the merged tree and names the sha it measured.
- [ ] Editing one census number in `docs/ARCHITECTURE.md` makes it exit non-zero, printing both values.
- [ ] `docs/ARCHITECTURE.md` states `measured at <sha>` next to the census.
- [ ] Wired into `check-docs`, not a new standalone workflow.
- [ ] `make lint`, `check-docs`, `check-wiring` exit 0.
