# 2026-11-02 repoint dead `published.yml` refs to `engine-build.yml`

Issue **#1580** (filed by the docs lane's own-domain audit).

## What changed

`published.yml` was deleted in `f244efe8` (#1027, merged #1029, 2026-10-30) and folded into
`engine-build.yml` as the sole engine producer (`tests/test_published_gate.py` states "published.yml
retired and engine-build the sole producer"), but three repo docs still cited it as an active
workflow. This change repoints every "current" citation to the true producer:

- **`docs/BOTS.md`** — the never-paused list and the publish/install-matrix prose now name
  `engine-build.yml`; the install/serve legs are described against the real
  `inputs.push == 'true'` / non-`none` gate (`test_published_gate`), not the retired
  `linux-published`-calls-`published.yml` wiring.
- **`docs/ARCHITECTURE.md`** — the `.github/workflows/` inventory drops the dead `published.yml`
  (`engine-build.yml` is already listed as the on-demand producer/sweep); the `install-published`
  leg prose moves to `engine-build.yml`'s `build` job, push-gated (issues #844 / #1027).
- **`README.md`** — the HF_TOKEN path is corrected to the reusable `pipeline.yml` via
  `secrets: inherit` (the true receiver; `engine-build.yml` receives no HF_TOKEN, so naming it would
  have been a new false claim).

Out of scope (left untouched, flagged on #1580): `bots/pause.toml` and `tests/test_bots_pause.py`
(pipeline-maintainer concern — `test_bots_pause.py:49` still asserts `published.yml` stays in
`never_pause`); `qa-validate.yml` cross-references are legitimate `trending-local-llms` sibling
workflow refs and are unchanged.

## Verified

- `grep -n 'published\.yml' docs/BOTS.md docs/ARCHITECTURE.md README.md` -> zero "current" citations
  (historical mentions elsewhere in the repo are untouched).
- Change-note direction (the #1123 loop): this note + its `docs/changes.d` index row.
- Doc gates at PR head: `check-docs` green (after this note), `check-wiring` rc=0,
  `check-architecture-census` rc=0.
