# fix-engine-bump-rebase-import

## ADDED Requirements

### Requirement: the file invocation can import the scripts package
`python3 scripts/engine_bump_rebase.py` MUST import `scripts.engine_bump_sync`.
The workflow MUST keep running that command. A missing `scripts` module MUST
fail the test that runs the file.

WHEN `python3 scripts/engine_bump_rebase.py --dry` runs from the repo root,
THEN it imports `scripts.engine_bump_sync` and does not raise
`ModuleNotFoundError: No module named 'scripts'`.

#### Scenario: the workflow command imports the shared module
- **Given** the repo root as the working directory
- **And** `GITHUB_TOKEN` is set to a value that cannot list pull requests
- **When** `python3 scripts/engine_bump_rebase.py --dry` runs
- **Then** the process exits 0
- **And** stderr does not contain `No module named 'scripts'`
- **And** stdout contains `[engine-bump-rebase] no open engine-bump PRs`
- **Test:** `tests/test_engine_bump_rebase.py::TestWorkflowYaml::test_file_invocation_imports_the_scripts_package`
