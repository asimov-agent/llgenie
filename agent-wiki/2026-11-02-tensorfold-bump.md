# 2026-11-02 tensorfold engine bump (re-pin `v1.2.4@a6720bed`)

Pull request **#2268**.

## What changed

The weekly engine-bump run re-derived tensorfold's install recipe at a newer upstream pin
(`ef27f74f` -> `a6720bed`, tagged `v1.2.4`) and applied it to the frozen cells:

- `containers/engines/dockerfiles/tensorfold/Dockerfile.cuda` — re-pinned and re-bootstrapped,
- `containers/engines/params/tensorfold.json`,
- `skills/engines/tensorfold/SKILL.md`,
- the affected `tests/` cases.

This PR changes no gate — CI builds and tests only tensorfold's own images.

## Note

The weekly tracking issue #107 is already closed; this bump implements no open issue and
closes nothing — it is the pinned-upstream-freshening step of that (completed) cadence,
recorded here under its PR.

The previous entry for the same cadence (#1519, `ef27f74f` v1.2.1) is superseded by this
re-pin; it names the `pinned` field moving forward so `check-engine-pins-published` for
tensorfold resolves the new tag once the producer publishes it.
