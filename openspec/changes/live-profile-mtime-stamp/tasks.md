# Tasks: live-profile-mtime-stamp (issue #2972)

## 1. Findings carry the file state they measured
- [x] `check_agent_profiles.py` live-comparison loop records the live mtime once per pair and
      both `live-longer` and `live-lines-missing` details name live size, live mtime (UTC ISO),
      and the run-start stamp (`run_stamp()` from `_STARTED`)

## 2. Green is as datable as red
- [x] `comparison_stats()` counts compared live/tree file pairs and their min..max live mtimes;
      the OK line prints the stamp `live comparison stamped: N file pair(s), live mtimes
      <min> -> <max>, run started <stamp>`; the audible SKIPPED line stays the explicit note
- [x] `skill_parity.py` OK line prints the same stamp shape (compared count, newest live mtime,
      run start) from `profile_drift`'s per-profile compared-pair stats

## 3. Verdicts untouched
- [x] exit codes unchanged: red fixture exits 1, clean mirror exits 0 (pinned in tests)

## 4. Tests pin the stamp format (red and green shapes, both scripts)
- [x] `tests/test_agent_profiles.py`: live-longer + live-lines-missing stamp pins (UTC ISO regex,
      run stamp present), OK-line stamp pin on a clean mirror
- [x] `tests/test_skill_parity.py`: OK-line stamp pin on a clean mirrored fixture

## 5. Final verification proofs (run before push)
- [x] `pytest tests/test_agent_profiles.py tests/test_skill_parity.py` rc=0
- [x] `make -s check-workflows` rc=0 and `make -s check-wiring` rc=0 (no wiring change)
- [x] `make -s openspec-validate NAME=live-profile-mtime-stamp` rc=0
- [x] `make test-unit` rc=0 on the committed head
