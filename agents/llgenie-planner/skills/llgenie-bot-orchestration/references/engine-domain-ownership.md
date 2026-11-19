# Engine-domain ownership: route `component:engine` work to the engine lane

Issue #2270. Companion to `domain-ownership-dispatch.md` (the discovery-vs-bump split);
this file is the ROUTING table for engine work items.

## The two-job split, measured on main

| job | target | what it enumerates |
| --- | --- | --- |
| pin bump | `make engine-bump-plan` (`MODE=plan`) | EXISTING pinned engines whose upstream sha moved — never new engines |
| new-engine discovery | `make render-engine-skill-gap` → `make check-engine-skill-gap` → `make spawn-engine-skill-issues` | engines the registry lists that no `skills/engines/*/SKILL.md` covers — one tracking issue per new engine |

The bump workflow therefore cannot "collect new engines": its denominator is
`load_skills()` (the skills already shipped). New engines arrive only through the
discovery path, and the tracking issues it spawns carry
`scripts/engine_skill_gap.py`'s label triple `bug` + `agent:implement` +
**`component:engine`**.

## Routing table (dispatch every row to exactly one lane)

| work item (what names it) | owner | why |
| --- | --- | --- |
| spawned engine-gap issue (`component:engine`, "has no llgenie skill") | `llgenie-engine-improver` | new-engine scaffold: skill stub, pinned build/serving params, engine matrix row, verify the CI rebuild — the profile names trending-engine sync and serving params |
| engine-bump PR needing repair (red engine-build cell, bad pin) | `llgenie-engine-improver` | the lane's five-step closed loop over the failing cell |
| engine serving/pin gate red at a live pin | `llgenie-engine-improver` | domain verification, per `domain-ownership-dispatch.md` |
| a defect in the engine-bump GATE SCRIPT itself (classifier/plan logic) | `llgenie-ci-pipelines-maintainer` | the #2073 two-trails negative control: the pipeline scripts are CI's, not the engine lane's |
| mechanical body/label/census hygiene on an engine PR | the implementer / vehicle author | mechanical half of the batch split; the engine lane never owns the push |

A `component:engine` issue is routed by the LABEL, not by a re-derived read of its
body: the spawn writes the domain marker itself, so routing is a field read, not an
interpretation. #2903/#2904 were spawned gap issues that closed through the generic
implementer queue precisely because the spawned issue carried no domain marker.

## Dispatch shape

- Cite the label row in the dispatch line: `component:engine -> llgenie-engine-improver`.
- Mechanical half stays with the implementer per `domain-ownership-dispatch.md` — one
  vehicle owns the push; the engine lane verifies through comments or its own vehicle,
  never both writing one branch.
- Before dispatching, `gh api repos/<repo>/issues/<n>/labels --jq '.[].name'` — the
  read-back, same endpoint the spawn writes through (#724 discipline).
