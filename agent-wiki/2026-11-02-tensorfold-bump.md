# 2026-11-02 tensorfold engine bump

Pull request **#1519**.

## What changed

The weekly engine-bump run re-derived tensorfold's install recipe at a newer upstream pin
(`812fb040` -> `ef27f74f`, tagged `v1.2.1`) and applied it to the frozen cells:

- `containers/engines/dockerfiles/tensorfold/Dockerfile.cuda` — re-pinned and re-bootstrapped,
- `containers/engines/params/tensorfold.json`,
- `skills/engines/tensorfold/SKILL.md`,
- the affected `tests/` cases.

This PR changes no gate — CI builds and tests only tensorfold's own images.

## Note

The weekly tracking issue #107 is already closed; this bump implements no open issue and
closes nothing — it is the pinned-upstream-freshening step of that (completed) cadence,
recorded here under its PR.
