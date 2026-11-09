# 2026-11-02 litert engine bump (re-pin `v0.19.1@7a03724c`)

Pull request **#2265**.

## What changed

The weekly engine-bump run re-derived litert's install recipe at a newer upstream pin
(`771b06e1` -> `7a03724c`, tagged `v0.19.1`) and applied it to the frozen cells:

- `containers/engines/dockerfiles/litert/Dockerfile.cpu` — re-pinned and re-bootstrapped,
- `containers/engines/params/litert.json`,
- `skills/engines/litert/SKILL.md`,
- the affected `tests/` cases.

This PR changes no gate — CI builds and tests only litert's own images.

## Note

The weekly tracking issue #107 is already closed; this bump implements no open issue and
closes nothing — it is the pinned-upstream-freshening step of that (completed) cadence,
recorded here under its PR.

The previous entry for the same cadence (#1517, `771b06e1` v0.19.0) is superseded by this
re-pin; it names the `pinned` field moving forward so `check-engine-pins-published` for
litert resolves the new tag once the producer publishes it.
