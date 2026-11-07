# census-scripts-map-bidirectional

Issue: [#2015](https://github.com/asimov-agent/llgenie/issues/2015)

## Why

`docs/ARCHITECTURE.md` §Scripts is the map of the `scripts/` tree, but the census gate that had kept
it honest checked only one direction: `_referent_problems` enforced `named-in-doc ⊆ tree` (a module
the doc names must exist). It never enforced `tree ⊆ named-in-doc` — a module joining `scripts/`
without a §Scripts row passed every gate forever. Measured at the census referent: 155 effective
`scripts/*.py|.sh` modules, 51 with no row in §Scripts, 13 named in no document at all.

## What changed

- **`scripts/check_architecture_census.py`** — added the coverage direction (`_coverage_problems`):
  every tracked `scripts/*.py`/`.sh` basename must appear in the §Scripts section (group row,
  `scripts/`-prefixed path, or trailing shell-leg prose); a module the tree holds but the map does
  not name reddens, naming it. The section is read with a hyphen-aware extractor
  (`_scripts_coverage_names`) so `fold-live-profile.py` is one name — never a phantom `profile.py` —
  and `scripts/tools/llgenie_harness.py`-style spellings resolve to their basenames. `_SCRIPTS_MAP_EXEMPT`
  (`__init__.py`, the package marker) is the only carve-out.
- **`docs/ARCHITECTURE.md`** — mapped all 51 previously-unmapped modules into their §Scripts group
  rows (or the trailing shell-leg prose).
- **Tests** — a negative control in `tests/test_architecture_census.py`: a tree module with no group
  row reddens the gate naming it; the existing subset test stays green (the reverse check is vacuous
  without a §Scripts section).

## Acceptance (verified)

- `make check-architecture-census` exits 0 on the mapped tree (coverage=0, referent=0).
- Negative control: `_coverage_problems` on a tree holding an unrrowd `orphan_module.py` names it and
  `check()` exits 1 with `scripts-map-coverage`.
- All 12 census tests pass; `make check-docs` green.
