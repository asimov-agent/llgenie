# 2026-11-16 — the lane profiles reference links the fleet-memory doc (issue #2064)

## What was verified

- Measured on `main`: the tree carries exactly **one** `agents/*/skills/*/references/agent-profiles*.md`
  (the ci-pipelines-maintainer profile is the only one with that reference), and it contained **0**
  occurrences of the `docs/BOTS.md` Fleet memory anchor — #2057 AC5's `agents/` side had never landed
  because docs PR #2063 was restricted to `docs/` by its own AC7.
- The reference's intro block now links `[docs/BOTS.md — Fleet memory]` via the exact anchor
  `#fleet-memory-one-hindsight-daemon-per-host-shared-plugin-profile-issue-2057` (copied byte-for-byte
  from BOTS.md's own cross-link at line 445), with a relative `../../../../../` path (the convention
  `agents/README.md` already uses for relative links).
- New hermetic test `tests/test_fleet_memory_pointer.py` (4 tests): the reference exists, every
  profiles reference carries the anchor, the anchor's heading target still exists in `docs/BOTS.md`,
  and a planted removal is caught. RED on the origin/main file (0 anchor occurrences), GREEN here:
  4 passed rc=0.
- Live re-sync: `make sync-agent-profile PROFILE=llgenie-ci-pipelines-maintainer` rc=0 — 115 files
  copied to `~/.hermes/profiles/llgenie-ci-pipelines-maintainer` and read back, 115 replaced an
  existing file, 5 with different content (the tree was ahead of live).

## Key decisions

- Pointer goes in the reference's intro so a lane sees it before the debt sections; the link names
  when to read it (adding a profile, wiring a new lane's memory, daemon-restart recovery).
- The test scans the glob, not the one file today's measurement names: a future second
  `agent-profiles*.md` inherits the requirement automatically.

## Current status

OpenSpec change `fleet-memory-pointer-2064` (proposal/spec/tasks). PR implements issue #2064;
issue closed once merged. SYNC line in the PR body records the live re-sync (issue #1724 rule).
