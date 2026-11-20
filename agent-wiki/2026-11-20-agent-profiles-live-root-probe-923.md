# agent-profiles live-root probe: an unreadable answer is an answer, not an exception (issue #923)

Issue: #923. PR: pending (feat/agent-profiles-live-root-probe-923).

## What was wrong (measured on `4f3fc1ef2`)

`HERMES_PROFILE_HOME=/nonexistent-home python3 scripts/check_agent_profiles.py` resolved the
profiles home to that path's PARENT — `/` — accepted it because `/` "exists", and the shape probe
then walked `/`, hit `/boot` (mode 700), and pathlib propagated the EACCES (`is_file`/`is_dir`/
`iterdir` raise, measured on 3.11). The whole gate aborted: `FAIL: the gate aborted before
finishing (PermissionError: '/boot/SOUL.md')`, exit 2, NOTHING checked — on the very probe whose
job is to decide a calm skip. The same vacuous-accept lived in `skill_parity.live_skills_root`,
which would report "comparing against live profiles at `/`" and exit 0 having compared nothing.

## What was verified against the spec

- New seam `holds_a_profile(base)` in `scripts/check_agent_profiles.py`: unlistable base →
  rejected; an unreadable candidate is skipped (it is an answer, not a fault) and the probe keeps
  looking. `live_root_info` and `skill_parity.live_skills_root` (same layer group, imported
  directly) both go through it — one reading, no second dialect.
- A rejected PROVIDED base is named in the skip line: `no profiles directory at
  $HERMES_PROFILE_HOME (its parent directory /)` — the reader sees which directory was rejected,
  not just which variable was set (#923 AC4). The no-variable wording is unchanged.
- Tests (4 new in `tests/test_agent_profiles.py`, fixture `SOUL.md` added in
  `tests/test_skill_parity.py`): mode-000 candidate inside a readable profiles home (comparison
  runs, rc 0); unlistable base mode-111 (skip names the base, caveat in the OK line, rc 0);
  provided var resolving to a profiles-less parent (skip names the parent); positive control —
  tree-prefix-of-live still reds `live-longer` (rc 1) through the hardened probe.
  `pytest tests/test_agent_profiles.py tests/test_skill_parity.py` → 158 passed.
- Host probes after the fix: the typo exits 0 with the skip caveat naming `/`; `make
  check-agent-profiles`, `make profile-drift`, `make lint`, `make check-docs` all exit 0 with the
  real host profiles (13) still compared.

## Decisions

- An unreadable entry is treated as "not a profile", never as a finding: the gate compares tree
  profiles against readable live homes and cannot assert anything about a directory no user can
  read; asserting a drift finding from an unreadable path would be unverifiable noise.
- The skill-parity `check` subcommand stays silent on a rejected base (host-only no-op, rc 0) —
  its loud line belongs to `report`, which is what a human reads.
- `skill_parity.py` imports `holds_a_profile` from the gate directly (same structural-gate layer,
  no `package-layers.json` edge needed): the #923 class must be fixed once, not mirrored.

## Current status

Implementation + tests green on the lane tree; full unit battery and preflight drive the PR.
