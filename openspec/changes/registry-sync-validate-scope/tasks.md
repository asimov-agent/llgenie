# Tasks

- [x] 1. File the issue with the measured evidence (issue #319): the bare `make skills-validate` validating the fixture, ci-unit's real scope, and the failing run's own tree (`1918e1a`) calling `REGISTRY=data/models.json` without `UNSUPPORTED` -> 7 errors.
- [x] 2. Pin the workflow's scope to `REGISTRY=data/models.json UNSUPPORTED=data/unsupported-engines.json`.
- [x] 3. Add the test that the sync job's scope equals ci-unit's.
- [x] 4. Prove the test fails on the pre-fix tree and passes after (rule 6c).
- [x] 5. Add an `agent-wiki/` entry citing #319.
- [x] 6. Verified: `make lint`, `make openspec-validate NAME=registry-sync-validate-scope`, `make check-wiring`, `make check-docs`, and the registry-sync tests green in the test image.
