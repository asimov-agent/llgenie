# 2026-11-02 strata engine bump

Pull request **#1518**.

## What changed

The weekly engine-bump run re-derived strata's install recipe at a newer upstream pin
(`3f6d9c28` -> `d94bac6a`, tagged `v0.2.9`) and applied it to the frozen cells:

- `containers/engines/dockerfiles/strata/Dockerfile.cuda` and `.rocm` — re-pinned and
  re-bootstrapped,
- `containers/engines/params/strata.json`,
- `data/strata_models.json`,
- `skills/engines/strata/SKILL.md`,
- the affected `tests/` cases, `docs/ARCHITECTURE.md` and `docs/BOTS.md`.

This PR changes no gate — CI builds and tests only strata's own images.

## Note

The weekly tracking issue #107 is already closed; this bump implements no open issue and
closes nothing — it is the pinned-upstream-freshening step of that (completed) cadence,
recorded here under its PR.
