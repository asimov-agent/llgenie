# 2026-11-02 sglang engine bump

Pull request **#1515**.

## What changed

The weekly engine-bump run re-derived sglang's install recipe at a newer upstream pin
(`35ce3132` -> `7df5dd09`, tagged `v0.5.23`) and applied it to the frozen cells:

- `containers/engines/dockerfiles/sglang/Dockerfile.cuda` and `.rocm` — re-pinned and
  re-bootstrapped (the shared base's prebuilt `lmsysorg/sglang` cell moves `v0.5.22` ->
  `v0.5.23`, and the params/doc rows follow the new pin),
- `containers/engines/params/sglang.json`,
- `skills/engines/sglang/SKILL.md`,
- the affected `tests/` cases and `docs/ENGINES.md`.

This PR changes no gate — CI builds and tests only sglang's own images.

## Note

The weekly tracking issue #107 is already closed; this bump implements no open issue and
closes nothing — it is the pinned-upstream-freshening step of that (completed) cadence,
recorded here under its PR.
