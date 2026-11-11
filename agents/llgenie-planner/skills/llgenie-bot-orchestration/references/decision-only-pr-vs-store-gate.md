# Decision records must ride the same PR as the store that names them

A "decision" record (deferred/Metal/etc. for an engine) cannot ship as a decision-only PR. The gate
`scripts/engine_skill_gap.py` builds `stale = [n for n in decisions if n in shipped_names or n not in reg_engines]`
(~lines 108-110) and `check()` errors on every stale entry (~227-229). So a decision for an engine the
**committed** `data/models.json` does not yet name is reported stale and reds `make check-engine-skill-gap`.

## The trap

The gate judges the **committed tree**, not the live store. An issue whose acceptance criterion is measured
against the live store (e.g. a 2026-10-31 store not yet in main) will look shippable, but a decision-only PR is
red by construction because CI runs the committed registry. This is the #1651/#673/#1654 conclusion.

## The correction

Decision entries land in the **SAME PR** as the store update that names them — the registry-sync store PR
(store + `unsupported-engines.json` + re-rendered `engine-skill-gap.json` in one commit). This is the repo's own
#229 pattern. Hold decision-only issues `parked` until the store vehicle advances; author the entries ahead of
time so they commit into that PR the moment it moves.

## Why it matters for dispatch

Do not dispatch a decision-only issue as `agent:implement` — it cannot produce a green PR alone. Park it, and
fold its authored entries into the store-sync issue's PR. #687 is the store-sync vehicle for such held decisions.
