# Re-cut the ARCHITECTURE census to a real ancestor so the docs gate stops reddening every PR (issue #1140)

## Why
`docs/ARCHITECTURE.md` stated the census `measured at \`3bba736e\`` — a real commit (PR #1214) that is
**not an ancestor** of `upstream/main` `d98c569c`. `make check-docs`'s census step
(`scripts/check_architecture_census.py`) requires the pointer to be an ancestor of HEAD, so the gate
reddened **every** open PR (my #1140/#1219 and unrelated #1220 both failed `scope`/`linux unit`
identically). The pointer was set by #1217 to a commit the merge didn't reach.

## What changed
- `docs/ARCHITECTURE.md`: the census block now states `measured at \`d98c569c\`` (a real, reachable
  ancestor) with the tree measured at that commit:
  `2442 tracked` (`data/` 10, `skills/` 17, `containers/` 57, `tests/` 221, `scripts/` 130,
  `openspec/` 1138, `agent-wiki/` 323, `docs/` 331), 187 `tests/test_*.py`, 291 changes, 323 entries.
- Numbers verified by the gate itself once re-pointed: `[census-gate] OK — census measured at
  \`d98c569c\` (tracked=2442, testspp=187, changes=291); referent \`d98c569c\` is an ancestor of HEAD`.

## Verified
`python3 scripts/check_architecture_census.py check` → `OK` (above). `make check-docs` → all three
steps green (`[changes-index] ok`, `[check-docs] ok`, `[census-gate] OK`). This is a document
re-record, not a gate weakening — the census gate still requires a real, reachable pointer with
matching numbers; it just points at the tree it can actually be measured on.
