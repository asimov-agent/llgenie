# Refreshing docs/ARCHITECTURE.md for the tree at 20261111T1959 (issue #2508)

## What changed

`docs/ARCHITECTURE.md` lagged the tree after the 2026-11-10/11 merge burst (#2474, #2478,
#2479, #2493, #2494, #2496, #2498 among others): the architecture bot re-derived the surface
and the drift from real `git` state and rewrote only the doc. PR #2509 carries it on
`agent/architecture-20261111T1959` (measured at `8a4bc26df0a7c132c0622204f7385c04fe46ccd5`).

Notable deltas in the re-derivation:

- Repository-layout census re-measured: 4500 -> 5414 tracked files; the nine named content
  dirs now sum to 5335; `agents/` 564 -> 1400 (the profile-fold PRs landed their tree copies),
  `openspec/` 1742 -> 1789 (461 changes), `agent-wiki/` 770 -> 785, `docs/` 780 -> 795,
  `tests/` 298 -> 300, `scripts/` 174 -> 175; a new `mk/` row (issue #800 include-split).
- The structural-gates row re-derived with the newer gates the 11-10/11 window added,
  including `check_file_hygiene.py` (issue #2484) and the host-space/reclaim family
  (issues #1583, #1624, #2141).
- The ci-verdict row carries the #2222 correction: a `RED` verdict says `RED`, never "no verdict".
- Suite census: 256 `tests/test_*.py` files, 237 in the gate.

## Current status

`docs/ARCHITECTURE.md` was the only file the bot commit touched (as
`Asimov Agent <support@docondee.com>`); this change-note trio (`agent-wiki/2026-11-11-architecture-refresh-2508.md`,
`docs/changes.d/2026-11-11-architecture-refresh-2508.md`, and its `CHANGES.md` index row) is the docs obligation
the refresh owed (`make check-docs`, issue #1123) — the pairing gate names it the change->note trio, so the branch
carries the doc plus the trio, exactly as merged refreshes #2363/#2474 did. The bot never merges and never
pushes to `main` — PR #2509 closes issue #2508.
