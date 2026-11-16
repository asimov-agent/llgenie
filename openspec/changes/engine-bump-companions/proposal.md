# engine-bump-companions — proposal

Issue: [#2865](https://github.com/asimov-agent/llgenie/issues/2865)

## Why

The weekly engine-bump lane opens a PR per changed engine, and every such PR was
red at `guard`, `scope`, `unit` and `ci-verdict` at their heads (2026-11-16 wave
#2855-#2859, all five). The lane staged its pin move — the skill, the params, the
Dockerfiles, `tests/ docs/ data/strata_models.json` — but shipped none of the
companions that PR gates require:

- the body named no active OpenSpec change, so the guard's openspec-change finding
  reddened `guard`;
- the commit changed behavioural surfaces (`scripts/`, `containers/`, `data/`)
  without adding an `agent-wiki/` note indexed by a `docs/changes.d/` row, so
  `check-docs`' change→note rule reddened `scope`;
- the frozen image-hash asserts the pin move itself made stale (e.g.
  `es._image_hash(params, "cuda") == "<hash>"` in `tests/test_engine_skills.py`,
  whose own docstring says "Update these only with a real vllm version bump")
  were never recomputed, so `unit` reddened.

Because the lane could not land a bump, engine pins aged against upstream, GHCR
engine tags stayed unpublished, and every weekly wave produced five permanently-red
PRs plus triage noise.

## What Changes

- `scripts/engine_bump.py::_companion_note`: after the pin/derive/apply/regen, the
  bump writes `agent-wiki/<date>-engine-bump-<id>.md` and its one-row
  `docs/changes.d/<date>-engine-bump-<id>.md` fragment, and rebuilds `CHANGES.md`
  from the fragments (`changes_index.write`), so the same commit that moves the pin
  also carries the note pair `make check-docs` owes it (issue #1123).
- `scripts/engine_bump.py::_rewrite_image_hash_asserts`: after regen, recompute each
  variant's image hash from the regenerated params and rewrite the frozen
  `== "<herox>"` equality asserts in test/docs files that reference this engine's
  params — a `!= "<hash>"` moved assert stays untouched.
- `scripts/engine_bump.py::bump()` wires both in, gated behind an explicit
  `emit_companions` argument that ONLY the lane entry points set (`main`'s `bump`
  and `bump_daily`, i.e. `make engine-bump`). `bump()` stays a safe library
  function: a unit test that drives it against a scratch tree never writes to the
  real repo.
- `.github/workflows/engine-bump.yml`: the PR body template now carries an
  `OPENSPEC: publish-changed-pin-images` line naming an active change (issue
  #1807), and the `git add` stages `agent-wiki/`, `docs/changes.d/` and
  `CHANGES.md` alongside the pin move so the companions reach the commit.

## Impact

- `scripts/engine_bump.py`, `.github/workflows/engine-bump.yml`
- `tests/test_engine_bump.py` (companion + image-hash + body/staging coverage)
- A bump head produced by this lane is green on a bump PR's `guard`, `scope` and
  `unit` companion grounds (`check-docs` gets its note, the guard gets its
  OPENSPEC name, the unit suite gets its fresh image hashes).
