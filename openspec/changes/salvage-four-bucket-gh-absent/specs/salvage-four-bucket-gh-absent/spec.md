# salvage-four-bucket-gh-absent

## ADDED Requirements

### Requirement: a missing gh executable is a failed call, never a traceback

`salvage-four-bucket.py`'s `run()`/`out()` helpers MUST treat a command absent from PATH (gh in
the unit-test container, git on a minimal image) exactly like any other failed call: catch
`FileNotFoundError`/`OSError` and return the empty/failed answer, never raise. The audit MUST then
continue, and when `shutil.which("gh")` is `None` MUST print a note to stderr that PR identity
could not be checked while still classifying branches by merge-base.

WHEN the audit is run in a shell where `gh` cannot be resolved
THEN it exits 0, prints no traceback, prints a note naming that PR identity could not be checked,
and reports its merge-base classification.

#### Scenario: the audit degrades with a note when gh is absent

- **Given** a git repo (with an `origin/main` and an orphan branch adding a path main lacks) run through the audit in a shell whose PATH cannot resolve `gh`
- **When** the audit runs
- **Then** it exits 0 with no `Traceback`, prints a note that gh / PR identity could not be checked, and still names the orphan branch
- **Test:** `tests/test_rebase_lane_scripts.py::test_the_audit_degrades_when_gh_is_absent`
