# 2026-11-10 freetoken engine bump

Pull request **#2438**.

## What changed

The weekly engine-bump run re-derived freetoken's install recipe at a newer upstream pin
(`ba31db2e` -> `5a73685b`, tagged `v0.2.2`) and applied it to the frozen cells:

- `containers/engines/dockerfiles/freetoken/Dockerfile.cuda` and `.rocm` — re-pinned and
  re-bootstrapped,
- `containers/engines/params/freetoken.json`,
- `skills/engines/freetoken/SKILL.md`,
- the affected `docs/ENGINES.md` and `tests/` cases.

This PR changes no gate — CI builds and tests only freetoken's own images.

## Note

The weekly tracking issue #107 is already closed; this bump implements no open issue and
closes nothing — it is the pinned-upstream-freshening step of that (completed) cadence,
recorded here under its PR.
