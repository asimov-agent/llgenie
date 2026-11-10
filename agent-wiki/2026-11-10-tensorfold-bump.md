# 2026-11-10 tensorfold engine bump

Pull request **#2440**.

## What changed

The weekly engine-bump run re-derived tensorfold's install recipe at a newer upstream pin
(`a6720bed` -> `b392ffce`, tagged `v1.2.5`) and applied it to the frozen cells:

- `containers/engines/dockerfiles/tensorfold/Dockerfile.cuda` — re-pinned and
  re-bootstrapped,
- `containers/engines/params/tensorfold.json`,
- `skills/engines/tensorfold/SKILL.md`,
- the affected `data/`, `docs/` and `tests/` cases.

This PR changes no gate — CI builds and tests only tensorfold's own images.

## Note

The weekly tracking issue #107 is already closed; this bump implements no open issue and
closes nothing — it is the pinned-upstream-freshening step of that (completed) cadence,
recorded here under its PR.
