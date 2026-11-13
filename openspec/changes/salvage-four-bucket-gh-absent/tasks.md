# Tasks — salvage-four-bucket-gh-absent

- [x] 1. `openspec/changes/salvage-four-bucket-gh-absent` — `proposal.md` + `specs/salvage-four-bucket-gh-absent/spec.md` (G/W/T, one scenario) + this checklist
- [x] 2. `salvage-four-bucket.py` — `run()` catches `(subprocess.SubprocessError, OSError)` and returns `None`, so a missing executable reads as a failed call and `out()` returns `""`
- [x] 3. `salvage-four-bucket.py` — when `shutil.which("gh")` is `None`, `main()` prints a degraded note (PR identity could not be checked) to stderr and still classifies by merge-base
- [x] 4. `tests/test_rebase_lane_scripts.py` — `test_the_audit_degrades_when_gh_is_absent` runs the audit in a real gh-less fixture repo and asserts rc=0, no traceback, the note, and the orphan classification
- [x] 5. `docs/changes.d/2026-11-13-salvage-four-bucket-gh-absent.md` + `agent-wiki/2026-11-13-salvage-four-bucket-gh-absent.md` + regenerated `CHANGES.md` row
- [x] 6. Verified: `tests/test_rebase_lane_scripts.py` all 27 pass; the new test fails on the pre-fix code (`FileNotFoundError: 'gh'`) and passes on the fixed code; `make lint`, `make check-docs`, `make check-wiring`, `make openspec-tasks-check`, `make check-pr-hygiene` pass
