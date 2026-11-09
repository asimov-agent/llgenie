# 2026-11-02 ollama engine bump (re-pin v0.40.15 @ 02480ca2)

Pull request **#2263**.

## What changed

The weekly engine-bump run re-derived ollama's install recipe at a newer upstream pin
(`f067033f` → `02480ca2`, tagged `v0.40.15`) and applied it to the frozen cells:

- `containers/engines/dockerfiles/ollama/Dockerfile.{cpu,cuda,rocm,vulkan}` — re-pinned and
  re-bootstrapped,
- `containers/engines/params/ollama.json`,
- `skills/engines/ollama/SKILL.md`,
- the affected `tests/` cases.

This PR changes no gate — CI builds and tests only ollama's own images.

## Note

The weekly tracking issue #107 is already closed; this bump implements no open issue and
closes nothing — it is the pinned-upstream-freshening step of that (completed) cadence,
recorded here under its PR.

The previous entry for the same cadence (#1521, `04088e7c` v0.40.13) is superseded by
this re-pin; a commit then moved the `pinned` field forward, so `check-engine-pins-published`
for ollama resolves the new tag once the producer publishes it.
