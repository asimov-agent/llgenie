# 2026-11-10 strata engine bump

Pull request **#2266**.

## What changed

The weekly engine-bump run first targeted Strata's newest release `v0.2.13` (`fb57f747`),
but that pin cannot link its rocm cell: `prefill.cpp` calls
`strata::prefill::fused::want_dm_f16`/`dm_f16_used` in an always-compiled source while the
definitions live in `moe_fused_iq.cu`, which CMake adds only under `STRATA_PREFILL_MMQ=ON`
(default OFF) — the link fails with `undefined symbol` (engine-build runs 42950150623 and
42956798213, both `completed failure`; the same call sites exist at `v0.2.12`, none at
`v0.2.11` or earlier). The bump therefore re-pinned to the newest release that links on
**all committed variants**, `d94bac6a` -> `4a416016` (`v0.2.9` -> `v0.2.11`), and applied it
to the frozen cells:

- `containers/engines/dockerfiles/strata/Dockerfile.cuda,rocm` — re-pinned and
  re-bootstrapped,
- `containers/engines/params/strata.json`,
- `skills/engines/strata/SKILL.md`,
- the affected `data/`, `docs/` and `tests/` cases.

This PR changes no gate — CI builds and tests only strata's own images.

## Note

The weekly tracking issue #107 is already closed; this bump implements no open issue and
closes nothing — it is the pinned-upstream-freshening step of that (completed) cadence,
recorded here under its PR. The `v0.2.12`/`v0.2.13` bumps are deferred to **#2486** until
upstream lands the link stubs (Niko1221/Strata pull request #5473, open).
