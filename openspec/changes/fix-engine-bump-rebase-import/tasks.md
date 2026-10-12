# fix-engine-bump-rebase-import — Tasks

Issue: [#214](https://github.com/asimov-agent/llgenie/issues/214)

- [x] 1. `scripts/engine_bump_rebase.py` adds the repo root to `sys.path` before importing `scripts.engine_bump_sync`.
- [x] 2. `tests/test_engine_bump_rebase.py::TestWorkflowYaml::test_file_invocation_imports_the_scripts_package` runs `python3 scripts/engine_bump_rebase.py --dry` and rejects `No module named 'scripts'`.
- [x] 3. The workflow command stays `python3 scripts/engine_bump_rebase.py`.
- [x] 4. `make openspec-validate NAME=fix-engine-bump-rebase-import` exits 0.
