# Architect SOUL stops teaching `manifest.json lists never-implement`

## What was verified

- Removed the stale sentence in `agents/llgenie-architect/SOUL.md` ("`agents/manifest.json`
  still lists `never-implement` for this profile; ... the tree PR has to drop
  `never-implement` or the gate will reject this soul") — the drop already landed at
  `dc94336f` (2026-11-01, PR #1259) and the manifest row is `["never-merge"]` (no
  `never-implement`) through the audit tip. The SOUL now states the current contract:
  `agents/manifest.json` lists `never-merge` only for this profile, and the host role rule
  ("structural design is this lane's PR") is operative.
- Fixed both duplicate reports of the same two lines: #2305 (filed from #2166's audit at
  `aef9ee7b`, which did not find #2240) and #2240 (filed at `bd55aaa0`). One SOUL change
  closes both — a second vehicle editing the identical lines would conflict and be hollow.
- `grep` at the new head: `still lists \`never-implement\`` and `tree PR has to drop
  \`never-implement\`` both return no hit in `agents/llgenie-architect/SOUL.md`.
- `agents/manifest.json` `llgenie-architect` row unchanged: `["never-merge"]`.
- `make check-agent-profiles` (CI mode, `HERMES_PROFILES_HOME=/nonexistent`) green;
  `make check-docs` green after the note + changes.d fragment. Live profile SOUL mirrored
  and `make sync-agent-profile PROFILE=llgenie-architect CHECK=1` byte-identical.

## What is at stake

A self-referential stale clause in the architect SOUL taught each session that its own
profile was still `never-implement`, claiming an unresolved obligation the manifest and the
pinning test (`tests/test_agent_profiles.py`) had both retired. A lane that believes it
still carries `never-implement` may defer structural-design PRs until "the manifest is
fixed" — exactly the self-misdiagnosis the drop was meant to end.

## Index

- Issue: #2305, #2240 (both are the same two-line stale claim; one vehicle closes both)
- PR: #<PR>
