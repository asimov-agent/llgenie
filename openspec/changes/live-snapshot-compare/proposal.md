# live-snapshot-compare

## Why

`make check-agent-profiles` / `make profile-drift` walk the live profiles directory and re-`stat()` /
re-read each counterpart file at every comparison point. The live tree is not frozen — another lane
rewrites it mid-run — so a `FAIL live-longer` can quote byte counts that already changed while the
run was still walking. Issue #2972 dated each finding; dating a moving read is still a read nobody
can re-check. Issue #2979 (the Not-covered half of #2972, landed by the PR closing #2972) asks for a
snapshot: read once, compare against that snapshot, and name the snapshot in every finding.

## What Changes

- `scripts/check_agent_profiles.py` gains a snapshot pass: before the tree/live walk, every compared
  live counterpart file is read exactly once into an in-memory snapshot recording size, mtime and a
  content sha256.
- All live-side comparisons (the size compare behind `live-longer`, the line-set compares, the
  live-only-file reports) consume the snapshot instead of re-touching the live path.
- Every live-side finding detail gains `live snapshot <sha12>` next to the existing size/mtime stamp;
  the OK comparison line gains the snapshot manifest count, so a reader can identify the exact bytes
  a run saw.
- Exit-code semantics are unchanged (red 1 / green 0 pinned by the existing fixture tests).

## Impact

- Affected specs: `live-snapshot-compare` (new capability; it completes the stamping landed by the
  change closing #2972).
- Affected code: `scripts/check_agent_profiles.py` (snapshot pass + detail rendering),
  `scripts/skill_parity.py` (report line), `tests/test_agent_profiles.py` (snapshot-consistency pins).
- No production gate semantics change: targets, exit codes and finding keys stay identical.
