# 2026-11-05 dead-vehicle guard — no force-push onto a merged/closed PR (issue #1733)

The rebase lane's ONLY merged/closed filter lives at decision time — `rebase_bot_sweep.py`
(`--state open`) — not at push time. Between the sweep picking a PR and `rebase_bot.sh`
force-with-lease-pushing it, a human can merge the PR; the force-with-lease guards a moved branch
TIP, not a closed/merged PR. A push onto a MERGED PR's branch is a dead-vehicle push: no
rebase-able branch exists, the push is discarded, the merge state reads as a null-state trap, and
the rebase lane re-verifies a closed PR. The same defect class produced the seven phantom #1751
refusals and #1749. This change closes the measure-window gap at the only moment that matters:

- `scripts/rebase_bot.sh`: immediately before `git push --force-with-lease`, a LIVE re-read
  (`gh pr view "$PR" --repo "$REPO" --json state,merged --jq ...`) hard-stops the run with a
  `gave-up` comment (branch untouched, no push) if `state != "open" || merged == true`, and also
  refuses (fail closed) when the re-read itself fails — a push that cannot prove the vehicle is
  open is a push on faith.
- `scripts/engine_bump_rebase.py`: `dead_vehicle_reason()` re-reads the LIVE PR
  (`/pulls/<n>`) through the same `api()` seam just before `sync_pr_with_main` force-pushes, and a
  closed / merged / unreadable PR is refused with a `gave-up` release (never `rebased`), skipping
  the sync entirely.
- Tests: `tests/test_rebase_bot_sweep.py` drives `rebase_bot.sh` for real in the existing
  scratch-repo harness (the fake `gh` now answers `pr view --json state,merged`) and asserts a
  merged PR stops the run with NO push and the branch untouched, and an unreadable state is
  fail-closed; `tests/test_engine_bump_rebase.py` asserts a merged PR is never synced and releases
  `gave-up`, and an unreadable re-read is fail-closed.

The re-read is the LIVE API at push time — never a blob-name or grep of a cached response, and the
sweep's decision-time `--state open` read is not reused as the push-time authority.

Verified: 122 rebase/engine tests pass (incl. the 4 new guard assertions); `make check-wiring`,
`make check-proc-gate`, `make check-docs` green. Baseline `origin/main@22347720`.

References: implements issue #1733.
