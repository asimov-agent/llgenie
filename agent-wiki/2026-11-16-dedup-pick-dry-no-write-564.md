# 2026-11-16 — `issue-dedup-pick DRY=1` previews the pair and writes nothing (issue #564)

## What was verified

- Defect measured on `main` (`28a3d43aa`): `pick()` (`scripts/issue_dedup.py:132`) had **no `dry`
  parameter**, the `Path("dedup-in.md").write_text(body)` (line 154) ran unconditionally, and
  `main()` (line 249) parsed `--dry` but called `pick(args.gh, args.repo)` without it. Probe on the
  origin/main copy confirmed: old signature `(gh: str, repo: str) -> dict | None`, no dry pass-through.
- Fix follows the refiner's #352 precedent exactly (`scripts/issue_refiner.py::pick(dry=False)` +
  `if not dry:` guard): `pick(gh, repo, dry=False)` and `main()` passes `args.dry`. Log wording is
  the `would write dedup-in.md` line #564 asked for; the protocol lines `action=pick`,
  `canonical=`, `copy=` are byte-identical, so the workflow's `sed -n 's/^action=//p'` parse keeps
  working and the agent leg's `dedup-in.md` input path is unchanged.
- New test `tests/test_issue_dedup.py::test_a_dry_pick_prints_the_pair_and_writes_nothing` drives
  the CLI path (`main(["pick", "--repo", …, "--dry"])`): prints the protocol + `would write
  dedup-in.md`, leaves no `dedup-in.md` in the tree, and a dry `pick()` returns the same decision a
  real pick would. RED on the origin/main script (no dry parameter at all), GREEN after the fix:
  module 15 passed rc=0; full `make test-unit` green rc=0 at this head.

## Key decisions

- Only `pick` was fixed; `apply_verdict` already honoured `--dry`. No `bots.mk`/Makefile change —
  the `DRY=1 -> --dry` wiring was already correct end-to-end up to the dropped argument.
- The refiner already prints `would write …, nothing written` (#352); the dedup wording mirrors it
  so the two preview bots log the same shape.

## Current status

OpenSpec change `dedup-pick-dry-no-write` (proposal/spec/tasks green under
`make openspec-validate`). PR implements issue #564; issue closed once merged.
