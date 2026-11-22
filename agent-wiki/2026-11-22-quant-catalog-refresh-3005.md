# Quant catalog refresh (issue #3005)

Date: 2026-11-22. Issue: #3005. OpenSpec change: `quant-catalog-refresh-3005`.

## What was verified
- The `ci-hf-live` battery was red on `main` (`46b15838e1`, run `45010151478`): `check-quant-catalog LIVE=1` called a committed unsloth plan gone (404/410). A local replay named a different link (`Q6_K_L`) gone minutes after `curl -I` answered 302×3 — a transient Hub flake, not a deletion.
- The mandated refresh chain (`sync-registry` → `sync-quant-catalog` → `render-trend-list-matrix` → `render-engine-skill-gap` → `skills-validate`) ran rc=0: 93 models / 2143 links (3 new links live-validated, incl. `nace-ai/Qwen3.8-27B-MLX`), 780 gated links, trend matrix 81 cases, skills 18/18 with 0 errors.
- `make -s spawn-engine-skill-issues DRY=1`: registry 50 engines, 18 skills, 0 unresolved — nothing to file.
- Battery seam re-probed green on the refreshed tree: `make check-quant-catalog` rc=0 (hermetic) and `make check-quant-catalog LIVE=1` rc=0.

## Key decision
The transient-404 classification itself (`_probe_status` treats any 404/5xx/transport as permanently dead) is out of scope for a data refresh and was filed as its own issue: #3007 (linked from this lane's PR `Not covered`).

## Current status
Data + fixtures landed through the lane branch `feat/quant-catalog-refresh-3005`; the battery's own verdict is its next green `main` run.
