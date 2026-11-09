# verify_lane_contract's roster derives from agents/manifest.json (issue #2316)

## What changed

`scripts/verify_lane_contract.py`'s roster is now ONE set: `agents/manifest.json`
is the source of truth for which lanes exist. The checker reads it (a new
`--manifest FILE` argument, default `<repo>/agents/manifest.json`) and checks
exactly the manifest's lanes; a live lane the manifest no longer lists is
reported as **drift**, never silently checked from whatever SOUL still sits
under `$HOME`. A manifest lane with no `DUTY` entry now FAILS naming the lane
as `manifest-lane-without-duty` (rc=1) instead of silently skipping its own-duty
check — a new lane added to the manifest is verified for its duty out of the
box, and the checker's `DUTY` keys can no longer drift from the manifest's
profile names. `tests/test_verify_lane_contract.py` drives the roster through a
scratch `--manifest`, keeps every existing negative control, and adds a
new-lane-without-duty negative control plus a subset referent test
(`manifest_lanes <= set(DUTY)`, never equality, so a legitimate new DUTY entry
does not red the suite). Live host still reports `13/13 lanes pass the
behavioural contract`.
