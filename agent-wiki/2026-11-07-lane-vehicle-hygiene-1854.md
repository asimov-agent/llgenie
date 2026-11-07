# lane-vehicle hygiene: fleet-witness + per-lane SYNC rule (#1854)

The rebase lane codified the regression guards behind finding #1854 (`measurement-and-readback.md`): the
fleet-witness rule reads a cited PR's `check-runs` conclusions from the API at the measured head (never a
`mergeable` status or a relayed "passed"), and the per-lane SYNC rule requires any profile-editing vehicle
under `agents/<lane>/` to carry its `SYNC: <profile> …` line in the same commit/push as the skill edit
(#1724). AC-1/AC-2 reference the now-CLOSED PR #1850 (satisfied as recorded on-issue); this vehicle
delivers AC-3, exercised by its own body carrying the `SYNC:` line. Issue: #1854.
