# tasks — fix-rebase-bot-push-reread-field

- [x] 1.1 attribute the push-time re-read rc=1: reproduce `gh pr view --json state,merged` with
      stderr and name the error (`Unknown JSON field: "merged"`)
- [x] 1.2 `scripts/rebase_bot.sh` re-read uses `--json state,mergedAt` with lowercased `.state`
      and `mergedAt != null` for the merged boolean
- [x] 1.3 the retry ring surfaces the read's stderr in the run log (no `2>/dev/null` masking)
- [x] 1.4 the actor test harness's fake `gh` validates the `--json` field list (rejects `merged`
      exactly like real gh), so a regression back to the dead spelling reddens the suite
- [x] 1.5 a permanent-read-error attribution test exists and refuses the push fail-closed
- [x] 1.6 `pytest tests/test_rebase_bot_sweep.py tests/test_rebase_lane_scripts.py` green
- [x] 1.7 `make openspec-validate NAME=fix-rebase-bot-push-reread-field` exits 0 and every task
      above is ticked
