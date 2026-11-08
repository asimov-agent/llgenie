# Verify the lane behavioural contract (issue #2260)

## What changed

`scripts/verify_lane_contract.py` is the orchestrator's per-pass answer to "do
they do what they are supposed to" — behavioural verification, distinct from
file drift. It checks each live lane's SOUL under `$HOME/.hermes/profiles/<lane>/`
(built from `pathlib.Path.home()`, never the tree and never a hardcoded account
path) against six contract elements: the `working on #` report line, the never-
merge rule, bookending, the issue+PR-under-`agents/<profile>/` versioning rule,
the lane's own duty (one regex per lane in the `DUTY` map), and a communication
commitment (`message_agent` / report to / recall) — plus a `skills-materialised`
axis (≥1 non-`.archive` `SKILL.md` to load). A FAIL names the lane and the
missing element; the script prints `N/13 lanes pass the behavioural contract`.

It is wired as orchestrator tick **step 9** (VERIFY LANE RESPONSIBILITY) in the
versioned procedure `agents/llgenie-planner/prompts/llgenie-orchestrator-tick.md`
(after dispatch; steps 9–13 renumbered to 10–14) and exposed as `make
verify-lane-contract` (host-only: a CI runner has no live profiles). A regression
is the PLANNER's fix, never the lane's own repair — the planner files a detailed
issue under `agents/<lane>/` and the lane lands the SOUL correction by PR.

## Negative controls (prove it is not a rubber stamp)

Hermetic `tests/test_verify_lane_contract.py` runs the real script with `--root`
against scratch fixtures: a complete contract PASSes; an empty SOUL FAILs; a SOUL
missing the report line FAILs `report-line`; a SOUL reporting to nobody FAILs
`communicate`; an `.archive`-only `skills/` FAILs `skills-materialised`; removing
a lane's own-duty marker reds that lane. Live host: 13/13 lanes pass at
`origin/main`.
