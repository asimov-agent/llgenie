# Tasks: trend-staleness-filing-3057

- [x] `scripts/trend_list_matrix.py`: `staleness_read` writes the named cells to
      `build/trend-staleness-drift.json` on exit 1, removes it on exit 0, leaves it on exit 2; bounded
      tests in `tests/test_trend_list_matrix.py` pin all three directions (synthetic fixture/live, no Hub)
- [x] `scripts/trend_staleness_issue.py`: file from the handoff when one exists (no `staleness_read` call);
      standalone re-read failure prints the FAIL line by name; tests pin handoff reuse (live build stubbed
      to raise) and the named standalone failure (print + exit code)
- [x] `.github/workflows/ci-hf-live.yml`: guard `make trend-staleness-issue || rc=$?` in the rc==1 branch,
      print the failing leg by name and `exit 3` on a filing failure; extend
      `tests/test_ci_hf_live_workflow.py` with the step-shape assertions (no exit-2 path through filing)
- [x] `python3 -m pytest tests/test_trend_list_matrix.py tests/test_trend_staleness_issue.py
      tests/test_ci_hf_live_workflow.py` rc=0 (104 passed, 0 skipped, 2026-11-26)
- [ ] `make test-unit` rc=0 and `make openspec-validate NAME=trend-staleness-filing-3057` rc=0
      (pre-push proofs)
- [ ] `make changes-index` rc=0 (agent-wiki entry + `docs/changes.d` fragment landed, issue #3057 named,
      side issue #3056 linked)
