# 2026-11-20 — live-profile findings carry their measurement stamps (issue #2972)

Issue: #2972 (the deferred half of #923's `Not covered`). OpenSpec change:
`live-profile-mtime-stamp`.

## What was verified

- The live-profile gates read a moving reference: the same live rulebook measured
  24,791 b then 21,349 b minutes apart. Findings now name the live file's size, its
  mtime (UTC ISO), and the check's own run-start stamp; the new `live-lines-missing`
  detail carries the same stamps the `live-longer` detail already had (#924).
- Green carries the same datability: `check_agent_profiles.comparison_stats()` stamps
  the OK line with the compared live/tree file-pair count, the min..max live mtimes,
  and the run start; `skill_parity.py`'s OK line stamps pair count, newest live mtime,
  and run start from `profile_drift`'s per-profile compared-pair stats (rels resolve
  against each mirrored `live_dir`, not the skills root).
- Stamping is message text only: red fixture exits 1, clean mirror exits 0 (pinned).

## Key decisions

- The SKIPPED line stays the explicit "not compared" note rather than a fake stamp
  (the gate cannot date a comparison that did not happen).
- Run-start stamp comes from the existing `_STARTED` (#924), exposed as `run_stamp()`;
  no new clock source.

## Current status

- `pytest tests/test_agent_profiles.py tests/test_skill_parity.py`: 163 passed.
- Adjacent pins (`test_rebase_lane_scripts`, `test_makefile_agents_mk_split`): 35 passed.
- Driven to a reviewable PR closing [issue 2972](https://github.com/asimov-agent/llgenie/issues/2972).
