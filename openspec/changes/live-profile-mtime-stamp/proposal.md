## Why

The live-profile gates (`make check-agent-profiles`, `make profile-drift`) compare the committed
tree against live profile files other lanes are editing at the same time. Measured on
2026-11-19/20: the same live rulebook read 24,791 b in one run and 21,349 b minutes later. A
`FAIL live-longer` line carries the live byte count and, since #924, a live mtime — but the
`live-lines-missing` shape carries neither mtime nor live size context, and the OK comparison
line names no timestamp at all: a green run is as undatable as a red one. Gate output that
cannot be dated is not evidence (issue #2972, the deferred half of #923's `Not covered`).

## What Changes

- `check_agent_profiles.py`: every live-comparison FINDING (`live-longer`, `live-lines-missing`)
  states, per compared file: live path, live size in bytes, live mtime (UTC ISO), and the run's
  own start timestamp.
- `check_agent_profiles.py`: the OK comparison line gains a stamp — number of compared file
  pairs, the min..max live mtimes seen, and the run's start time. The existing audible SKIPPED
  line already states when comparison did not happen and stays as-is.
- `skill_parity.py`: the OK line carries the same stamp shape over the mirrored skill surface
  (compared file count, newest live mtime, run start); `profile_drift` records per-profile
  compared-pair stats to make that computable.
- Exit codes are NOT touched: stamping is message text only (`check-agent-profiles` /
  `profile-drift` verdicts keep their current meaning).

## Impact

- Modified capabilities: agent-profiles gate report lines, skill-parity report lines.
- Added tests pinning the stamp format for the red (`live-longer`, `live-lines-missing`) and
  green (OK line) shapes, in both scripts' test files.
- No new make targets, no CI sequence changes, no exit-code changes.
