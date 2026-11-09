# engine-bump-rebase-behind-live-main — tasks

- [x] `pr_is_behind(pr, repo, run_git)` resolves the live main head SHA from `upstream_main(repo)` and compares the PR head against it (never `pr['base']['sha']`); unresolvable -> fail closed `behind`
- [x] thread `repo` + `run_git` from `main()` into `pr_is_behind`
- [x] unit test `test_stale_recorded_base_but_head_behind_live_main_is_behind` locks the #2266 classification (recorded base lags, head lacks live main -> behind)
- [x] unit test that an unresolvable live main head is fail-closed behind
- [x] `tests/test_engine_bump_rebase.py` green (20/20 incl. the #2383 lock)
- [x] `make test-unit` green
- [x] change-note trio (agent-wiki + docs/changes.d + CHANGES.md) keyed to #2383
- [x] openspec spec + proposal + tasks
- [x] one PR closing #2383; never merge
