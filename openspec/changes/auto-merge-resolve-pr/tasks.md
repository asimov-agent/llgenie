# Tasks — auto-merge-resolve-pr

- [x] 1. OpenSpec change: proposal, spec, this checklist
- [x] 2. `.github/workflows/auto-merge.yml`: tolerate a 404 from the runs endpoint, search by branch
- [x] 3. `tests/test_auto_merge.py`: the workflow text carries both guards
- [x] 4. README + agent-wiki
- [x] 5. Verified: `pytest tests/test_auto_merge.py -k 'fork_run or workflow_run_on_ci'` → 2 passed
