# 2026-11-02 litert engine bump

Pull request **#1517**.

## What changed

The weekly engine-bump run re-derived litert's install recipe at a newer upstream pin
(`bda62485` -> `771b06e1`, tagged `v0.19.0`) and applied it to the frozen cells:

- `containers/engines/dockerfiles/litert/Dockerfile.cpu` — re-pinned and re-bootstrapped,
- `containers/engines/params/litert.json`,
- `skills/engines/litert/SKILL.md`,
- the affected `tests/` cases.

This PR changes no gate — CI builds and tests only litert's own images.

## Note

The weekly tracking issue #107 is already closed; this bump implements no open issue and
closes nothing — it is the pinned-upstream-freshening step of that (completed) cadence,
recorded here under its PR.
