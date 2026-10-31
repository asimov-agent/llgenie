# import-roots-baseline-set-shaped

## ADDED Requirements

### Requirement: ratchet-diffs-site-sets

`scripts/check_import_roots.py ratchet` SHALL refuse a tree by comparing per-rule
`tests/fixtures/import-roots-baseline.json` **site sets**, not counts: a site present in the tree now
and absent from the baseline is a refusal naming exactly that `file:line`; a site recorded in the
baseline and absent now is the reported, allowed shrink. Exit code SHALL be `1` on any refusal and `0`
when every rule's current sites are a subset of (or equal to) the recorded set or the recorded count
for a legacy count-shaped baseline.

#### Scenario: a planted root reds naming exactly its file:line

- **Given** a tree whose set-shaped baseline records `"sys-path": {"count": 1, "sites": ["tests/test_x.py:2"]}`, and a further module-level `sys.path` entry added at `tests/test_new.py:2`
- **When** `python3 scripts/check_import_roots.py ratchet --root <tree>` runs
- **Then** it exits 1 and its output names `tests/test_new.py:2` exactly — never the recorded `tests/test_x.py:2` alongside it
- **Test:** `tests/test_import_roots.py::test_the_ratchet_refusal_names_exactly_the_new_file_and_line`

#### Scenario: removing a root is green and reports the shrink

- **Given** a set-shaped baseline recording `"sys-path": {"count": 2, "sites": ["tests/test_x.py:2", "tests/test_y.py:1"]}` and a tree whose only current site is `tests/test_x.py:2`
- **When** the ratchet runs
- **Then** it exits 0 and its output names `tests/test_y.py:1` as the removed (allowed) site
- **Test:** `tests/test_import_roots.py::test_the_ratchet_reports_a_removed_root_as_the_allowed_shrink`

#### Scenario: a clean tree is green and prints no site

- **Given** a tree whose current sites equal its recorded set
- **When** the ratchet runs
- **Then** it exits 0 and prints no site line
- **Test:** `tests/test_import_roots.py::test_the_ratchet_is_green_and_names_no_site_when_nothing_was_added`

#### Scenario: a legacy count-shaped baseline still ratchets

- **Given** a baseline whose `"sys-path"` entry is a plain integer (the pre-#1101 shape) and a tree whose current count is above it
- **When** the ratchet runs
- **Then** it exits 1, names the rule's sites, and carries a note to re-record once with `--update`
- **Test:** `tests/test_import_roots.py::test_a_legacy_count_baseline_still_ratchets`
