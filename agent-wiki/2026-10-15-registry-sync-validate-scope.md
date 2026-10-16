# 2026-10-15 — issue #319: the registry sync validates the registry it synced

Part of the "exercise every bot dispatcher one at a time" sweep. `registry-sync.yml`'s scheduled runs
fail at `skills-validate`, so `chore/registry-sync` is never pushed and no sync PR opens.

## What was found

The job's own gate validated the wrong data. On `main` the step ran `make skills-validate` with no
overrides, so it fell back to the Makefile default — the small fixture
(`tests/fixtures/trending-models.json`) — while `ci-unit` runs the real registry
(`Makefile:928`: `$(MAKE) skills-validate REGISTRY=data/models.json UNSUPPORTED=data/unsupported-engines.json`).

The 12/13 Oct failures are the earlier form of that line: the failing run's own tree (`1918e1a`) had
`make skills-validate REGISTRY=data/models.json` with NO `UNSUPPORTED`, so the 7 engines already
recorded in `data/unsupported-engines.json` were hard errors
(`registry engine 'mlx-serve' has no skill`) and the job died before pushing.

## What was done

- OpenSpec change `registry-sync-validate-scope` created FIRST via the containerized CLI
  (`make openspec-new`), validated, all tasks ticked.
- `.github/workflows/registry-sync.yml`: the validation step now runs the SAME scope `ci-unit` uses —
  `make skills-validate REGISTRY=data/models.json UNSUPPORTED=data/unsupported-engines.json` — with
  a comment naming why both omissions are wrong.
- `tests/test_registry_sync_trend.py`: new test reads the workflow's step AND `ci-unit`'s own line
  out of the Makefile and asserts the two scopes match, so they cannot drift apart again.

## Verified

- `tests/test_registry_sync_trend.py -k "sync_job_validates or october_5_fixture"` in
  `llgenie/test:latest` (`:ro`): 3 passed.
- Rule 6c: the new test FAILS on main's workflow step and passes with the fix.
- `make skills-validate REGISTRY=data/models.json UNSUPPORTED=data/unsupported-engines.json` on
  current main: `16 skills, registry 24 engines, 0 error(s)` — the same call without the decisions
  file is where the 12/13 Oct runs died.
- `make lint`, `make openspec-validate NAME=registry-sync-validate-scope`, `make check-wiring`,
  `make check-docs` green.

## Status

- Branch `fix/registry-sync-validate-scope`, PR against `asimov-agent/llgenie:main`, `closes #319`.
- Not covered: #318 (the `engine-bump-rebase.yml` push-run anomaly).
