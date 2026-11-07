# census-scripts-map-bidirectional

## Why

`docs/ARCHITECTURE.md` §Scripts is the map of the `scripts/` tree (five groups — Product path,
Security pipeline, Structural gates, CI entrypoints, Bots and automation — plus two trailing prose
paragraphs). The census gate that keeps that map honest checks only ONE direction:
`scripts/check_architecture_census.py::_referent_problems` enforces `named-in-doc ⊆ tree` (a module
the doc names must exist at the referent sha). It never enforces `tree ⊆ named-in-doc` — a module
that joins `scripts/` without a row in the §Scripts section passes every gate forever.

Measured at the census referent on main: 155 effective `scripts/*.py|.sh` modules, 51 of them with
no row in the §Scripts section. The map a reviewer reads to place a new module silently shrinks: a
third of the tree has no group, and 13 are named in no document at all. Nothing reddens.

## What Changes

1. **Extend `scripts/check_architecture_census.py` with the coverage direction `tree ⊆ named`.** A
   `_coverage_problems(ref)` check lists every tracked `scripts/*.py`/`.sh` basename at the referent
   that the §Scripts section does not name; the gate reddens naming each. The section is read with a
   hyphen-aware extractor (`_scripts_coverage_names`) that recognises basenames, `scripts/`-prefixed
   paths, and hyphenated names (`fold-live-profile.py`), so the map's own spellings resolve. A dated
   `_SCRIPTS_MAP_EXEMPT` set (`__init__.py` — the package marker, stated but never rowed) is the only
   carve-out.
2. **Map the currently-unmapped modules into the §Scripts section.** 51 modules get a row in their
   correct group (Product path, Security pipeline, Structural gates, CI entrypoints, Bots and
   automation) or into the trailing shell-leg prose; the 13 named in no document at all land in a
   group row like any other.
3. **Prove the reverse direction by its own negative control.** A tree whose referent holds a
   `scripts/*.py` module absent from §Scripts must exit 1 naming that module; the mapped real tree
   must exit 0.

## Impact

- `scripts/check_architecture_census.py` — adds `_coverage_problems`, `_scripts_coverage_names` and
  `_SCRIPTS_MAP_EXEMPT`; wires the coverage finding into `check()`; makes `_referent_problems` read
  the section with the hyphen-aware extractor (the plain `\w`-only regex would capture a phantom
  `profile.py` out of `fold-live-profile.py`).
- `docs/ARCHITECTURE.md` — maps every previously-unmapped `scripts/` module into the §Scripts section.
- `tests/test_architecture_census.py` — a negative-control test asserting the reverse direction fires
  and names the unmapped module; the existing subset test stays green (the reverse check is vacuous
  when no §Scripts section exists).
- `agent-wiki/` + `docs/changes.d/` + `CHANGES.md` — the #1123 change-note trio.

## Out of Scope

#795 (declare the five groups as import-layering data + break the engine_bump↔engine_params_derive
cycle) touches the same groups table but is a LAYERING gate over imports; this change is the
map-coverage direction of the census gate — a distinct mechanism and file set. It does not change the
census's referent semantics (counts stay measured at the `measured at <sha>` pointer, an ancestor of
HEAD — issue #1053).
