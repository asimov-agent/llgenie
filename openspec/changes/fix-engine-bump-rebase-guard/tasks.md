# fix-engine-bump-rebase-guard — Tasks

Issue: [#212](https://github.com/asimov-agent/llgenie/issues/212)

- [x] 1. The rebase guard sends `Authorization: Bearer $TOKEN` with `TOKEN` set to `secrets.GITHUB_TOKEN`.
- [x] 2. `tests/test_engine_bump_rebase.py::TestWorkflowYaml::test_guard_sends_the_token_variable` locks that header on `ci.yml`, `engine-bump.yml`, `engine-bump-rebase.yml`, and `registry-sync.yml`.
- [x] 3. README names `engine-bump-rebase.yml` in the collaborator guard and states the `$TOKEN` header.
- [x] 4. `make openspec-validate NAME=fix-engine-bump-rebase-guard` exits 0.
