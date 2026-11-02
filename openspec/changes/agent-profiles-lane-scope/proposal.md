---
name: agent-profiles-lane-scope
about: check-agent-profiles gains a per-lane --profile scope and a repository-wide committed-tree ratchet
status: active
---

# Scope check-agent-profiles to a lane's own profile, and ratchet the fleet tree (issue #1090)

## Proposal

`make check-agent-profiles` runs `scripts/check_agent_profiles.py check` — a fleet-wide report whose
**exit code is shared by every lane.** The unit tests `tests/test_agent_profiles.py` drive
`findings()` / `main([…])`, and the clean-tree ones assert the GLOBAL verdict. On a host where another
lane's live profile has drifted (three lanes did within one hour while their PRs sat parked), a lane
whose own profile is correct still goes red — because of another lane's live edit, which the lane must
not touch.

This change keeps the global check **loud and unchanged** and adds a per-lane escape hatch plus a
fleet-wide ratchet:

- `--profile <name>` filters findings to that lane's own paths plus the manifest/fleet findings every
  lane shares — a strict subset of the global set (`scoped ⊆ global`), so a lane whose own profile is
  clean greens despite other lanes' live drift.
- The committed tree's findings are ratcheted against
  `tests/fixtures/agent-profiles-baseline.json` (set-shaped, import-roots #953/#796 style), so a NEW
  committed-tree finding in any lane still reds the fleet — the global protection #791 added cannot rot
  silently through the scoped view.
- The seven tree-only tests that asserted the global verdict on a clean fixture get their live home
  isolated, so a lane's own test passes on a drifted host without weakening the assertion.

## Motivation

A gate is only trustable if each lane's own PR can green when it did its part. Today the least-drifted
lane pays for everyone's live edits; the only workaround is editing an assertion, which is exactly the
drift mechanism #791 exists to prevent.

## Change

`scripts/check_agent_profiles.py`: `--profile NAME` (validated against the manifest, unknown name exits
2) filters `findings()` to `_profile_of(where) in (None, NAME)`; `--ratchet` refuses committed-tree
findings past the recorded baseline; `--update-baseline` re-records it. `Makefile`:
`check-agent-profiles-ratchet` wired into the CI gate list beside `check-import-roots`.
`tests/test_agent_profiles.py`: seven host-fragile tests isolate their live home; five new tests assert
scoped ⊆ global, a clean lane greens under `--profile` despite a drifted sibling, unknown profile exits
2, every committed lane passes `--profile <own>`, and the ratchet refuses a new committed-tree finding.
`tests/fixtures/agent-profiles-baseline.json`: the tree-only finding baseline (currently `{}`).
`agent-wiki/` note + `docs/changes.d/` fragment + `make changes-index`. `openspec/changes/` change.
