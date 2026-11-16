# chore: the engine-bump lane emits the companions a bump PR needs

Issue: [#2865](https://github.com/asimov-agent/llgenie/issues/2865)

## Why

The 2026-11-16 bump wave opened five PRs (#2855-#2859) and all five went red
for the same lane defects, measured from CI logs and scratch clones at each
head:

- guard red: every bump body lacks an `OPENSPEC:` line, and
  `make check-pr-hygiene` requires one referencing an active change for a diff
  that touches product code (`containers/`, `scripts/`);
- scope red: a bump touches `containers/` with no `agent-wiki/` note, no
  `docs/changes.d/` row, and no OpenSpec artifact
  (`test_the_report_names_documented_missing_work_records_and_the_index`);
- unit red: `_rewrite_pin_asserts` rewrites only `tests/` and `docs/` - it
  (a) rewrites historical `docs/changes.d/` rows (measured on #2857:
  `2026-11-15-llama.cpp-bump.md` gained `b903f867` from the bump), leaving the
  docs report with undocumented records, and (b) never rewrites the engine's
  own SKILL.md, so `make generate-engine-params` back-fills the old base tag
  into the params (measured on #2858: dockerfile `vllm-openai:v0.34.0` vs
  params `"base": ...v0.33.0`, test literal frozen at `v0.33.0`);
- unit red: regen moves each variant's image-hash half of the published tag
  while `tests/test_engine_skills.py` asserts the old hashes (measured on
  #2858: regen emits `4c1f3eee` -> `4d7140a3` cuda / `f5a3030b` cpu, four
  frozen asserts);
- unit red: `test_ci_publish_order.py` case 2 asserts a bumped engine's params
  file must not look deferred, but a pin bump retags without touching the
  params file - the test must branch on `retagged_engine_ids` like the rule it
  cites (issue #823).

## What Changes

- `scripts/engine_bump.py` generates the companion pair for every bump:
  `agent-wiki/<date>-<engine>-bump.md` plus the matching
  `docs/changes.d/<date>-<engine>-bump.md` row, referencing the bump lane.
- `.github/workflows/engine-bump.yml` stages `agent-wiki/` and appends
  `OPENSPEC: publish-changed-pin-images` (the active change covering this
  lane) to the PR body.
- `_rewrite_pin_asserts` no longer rewrites `docs/changes.d/` history rows,
  and additionally rewrites current-pin literals (base tags, image-tag tokens)
  inside the bumped engine's own SKILL.md.
- After `make generate-engine-params` regenerates params, the lane rewrites
  frozen image-hash asserts and tag literals for the bumped engine in
  `tests/` (lines naming `_image_hash(` or the engine's image tag), mirroring
  the #2553 precedent.
- `test_ci_publish_order.py` case 2 defers an engine that
  `retagged_engine_ids` names, even when its params file equals base.

## Impact

- `scripts/engine_bump.py`, `.github/workflows/engine-bump.yml`
- `tests/test_ci_publish_order.py`, `tests/test_engine_bump_pr_body.py`
  (updated), new `tests/test_engine_bump_companions.py`
- Affected: `tests/test_engine_skills.py` frozen literals move on the next
  lane run instead of reddening it.
- The next weekly lane run (Monday 06:53 UTC) re-measures #2855-#2859: the
  lane reuses their branches and PRs.
