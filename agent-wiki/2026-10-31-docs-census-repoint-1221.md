# Re-point the ARCHITECTURE census at an ancestor so every PR's scope/check-docs unblocks (#1221)

## What changed

`docs/ARCHITECTURE.md`'s census `measured at <sha>` pointer named `3bba736e` — a real commit, but
set by merged PR #1217 to a `#1214` branch head (`34ad88f0` re-pointed it) that the squash re-authored
out of main's first-parent lineage. `check_architecture_census.py` requires the pointer to be a real
commit **AND an ancestor of HEAD** (issues #896, #1053), so it had *no usable referent* and every PR's
`scope/check-docs` red regardless of its own diff (`[census-gate] the census has no usable referent`).

Re-pointed the census at the current main `d98c569c` (an ancestor of HEAD now and forever after PRs
merge) and set the numbers to the tree AT that sha, measured mechanically with the gate's own
`measure(<ref>)` — never hand-guessed:

| claim | before (at `3bba736e`) | after (measured at `d98c569c`) |
|---|---|---|
| tracked | 2440 | 2442 |
| `agent-wiki/` | 322 | 323 |
| `docs/` | 330 | 331 |
| `agent-wiki` entries | 322 | 323 |
| `testspp` (`tests/test_*.py`) | 187 | 187 (unchanged) |
| openspec changes | 291 | 291 (unchanged) |

The gate is **not weakened**: the pointer must still be a real commit that is an ancestor of `HEAD`,
and the numbers must still equal the tree at that sha.

## Evidence (measured at the PR head `d98c569c`)

```
[census-gate] OK — census measured at `d98c569c` (tracked=2442, testspp=187, changes=291);
              referent `d98c569c` is an ancestor of HEAD (d98c569c)     # make check-architecture-census
[check-docs] ok ... 324 agent-wiki/ entry references ...                  # full check-docs green
```

`make check-architecture-census` (wired into `check-docs`) is green on a clean merge-tree of
`origin/main` and on every PR rebased onto it, because `d98c569c` remains an ancestor.

## Acceptance

- [ ] `docs/ARCHITECTURE.md` census pointer is a real commit that is an ancestor of `HEAD`.
- [ ] `make check-architecture-census` green; tracked/testspp/changes = the tree at `d98c569c`.
- [ ] Fix forward; gate unweakened; #1217 not reopened.
