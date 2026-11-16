# 2026-11-16 — engine-bump companions (issue #2865)

## Problem
The weekly engine-bump lane opened a PR per changed engine (#2855-#2859, the
2026-11-16 wave), and all five were red at `guard`, `scope`, `unit` and
`ci-verdict` at their heads. The lane staged its pin move — skill, params,
Dockerfiles, `tests/ docs/ data/strata_models.json` — but shipped none of the
companions the PR gates require:

- the bump body named no active OpenSpec change, so the guard's openspec-change
  finding reddened `guard`;
- the commit changed behavioural surfaces without adding an `agent-wiki/` note
  indexed by a `docs/changes.d/` row, so `make check-docs`' change→note rule
  reddened `scope`;
- the frozen image-hash asserts that the pin move itself made stale (e.g.
  `es._image_hash(params, "cuda") == "<8hex>"` in `tests/test_engine_skills.py`)
  were never recomputed, so `unit` reddened.

Because the lane cannot land a bump, engine pins age against upstream, GHCR tags
stay unpublished, and every wave produces five permanently-red PRs.

## Fix
- `scripts/engine_bump.py::_companion_note` writes the dated `agent-wiki/
  <date>-engine-bump-<id>.md` note and its one-row `docs/changes.d/` fragment and
  rebuilds `CHANGES.md`, so the same commit that moves the pin carries the note
  pair `make check-docs` owes it (issue #1123).
- `scripts/engine_bump.py::_rewrite_image_hash_asserts` recomputes each variant's
  image hash from the regenerated params and rewrites the frozen `== "<hash>"`
  equality asserts in test/docs files that reference `params/<id>.json` — a
  `!= "<hash>"` moved assert stays untouched.
- `bump()` gates both behind an explicit `emit_companions` argument that only the
  lane entry points set (`main`'s `bump` and `bump_daily`, i.e. `make
  engine-bump`); a library caller never writes to the real repo.
- `.github/workflows/engine-bump.yml` adds `OPENSPEC: publish-changed-pin-images`
  (issue #1807) to the PR body and stages `agent-wiki/`, `docs/changes.d/` and
  `CHANGES.md` in the `git add` alongside the pin move.

## Benefit
A bump head produced by the fixed lane is green on a bump PR's `guard`, `scope`
and `unit` companion grounds: the guard sees its OPENSPEC name, `check-docs` gets
its note, and the unit suite gets its fresh image hashes. Engine pins stay rolling
and GHCR tags reach the registry instead of piling up.

## Verified
- `tests/test_engine_bump.py`: `test_bump_writes_the_companion_note_and_row`,
  `test_bump_rewrites_frozen_image_hash_asserts`,
  `test_bump_pr_body_carries_openspec_line_and_stages_companions` all pass; the
  full `make test-unit` suite (aggregated) stays green (78 passed in
  `tests/test_engine_bump.py`).
- The lane writes are gated: the pre-existing bump fixtures that drive `bump()`
  as a library still pass without a companion write.

Issue: #2865 (implements the companion seam); companion of #1123 (change→note),
#1807 (OPENSPEC body line).
