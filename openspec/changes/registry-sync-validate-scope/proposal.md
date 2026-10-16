# The registry sync's own gate must validate the registry it synced (issue #319)

**Issue:** [#319](https://github.com/asimov-agent/llgenie/issues/319)
**Capability:** `registry-sync-validation-scope`

## Why

`registry-sync.yml`'s post-sync validation does not validate the file the job just regenerated.

On `main` the step runs `make skills-validate` with no overrides, so it falls back to the Makefile
default — the little fixture:

```
$ make skills-validate
python3 scripts/engine_skills.py validate --registry "tests/fixtures/trending-models.json"
[skills-validate] 16 skills, registry 16 engines, 0 error(s)
```

while `ci-unit` runs the real one (`Makefile:928`):
`$(MAKE) skills-validate REGISTRY=data/models.json UNSUPPORTED=data/unsupported-engines.json`.

So the sync job's own gate can pass while the `data/models.json` it is about to push fails the same
check in CI. The 12/13 Oct scheduled failures are the earlier form of the same line: the failing
run's own tree (`1918e1a`) had `make skills-validate REGISTRY=data/models.json` with **no**
`UNSUPPORTED`, so the 7 engines already recorded in `data/unsupported-engines.json` were hard
errors, the job died there, and no `chore/registry-sync` PR was ever opened.

## What Changes

- **`.github/workflows/registry-sync.yml`** — the validation step calls
  `make skills-validate REGISTRY=data/models.json UNSUPPORTED=data/unsupported-engines.json`, the
  SAME scope `ci-unit` uses, so the job validates the data it is about to push.
- **`tests/test_registry_sync_trend.py`** — a test reads the sync workflow's step and `ci-unit`'s own
  line from the Makefile and asserts the two scopes match, so they cannot drift apart again.

## Impact

A sync run now fails on the registry it synced (the correct gate) instead of silently validating a
fixture, and the unsupported-engine decisions are honoured so a legitimately-recorded engine no
longer kills the run.

## Not covered

- The historical failing runs themselves (no action — they are the evidence).
- #318 (the `engine-bump-rebase.yml` push-run anomaly) — separate.
