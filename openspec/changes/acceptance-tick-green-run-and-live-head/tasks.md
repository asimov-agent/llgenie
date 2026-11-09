# Tasks — acceptance-tick-green-run-and-live-head (issue #2288)

Issue: [#2288](https://github.com/asimov-agent/llgenie/issues/2288)

- [x] 1. `scripts/check_pr_acceptance.py` re-checks each TICKED criterion's cited `run=<id>` against
      the live `gh run view` conclusion and holds a tick whose run did NOT conclude `success`
      (`tick-red-run`, blocking) — a by-design guard-red run can never stand as proof.
- [x] 2. `scripts/check_pr_acceptance.py` holds a ticked criterion whose cited `head=<sha>` /
      `live=<sha>` is not the merge-time head (`tick-stale-head`, blocking), using `--rev` as the
      referee only when it is a sha.
- [x] 3. `scripts/review_finalize.py` appends the PR's live head as a `live=<sha>` twin beside every
      `head=<sha>` it writes (`with_live_head`, idempotent) so a rebased tick is visible as stale.
- [x] 4. Tests in `tests/test_check_pr_acceptance.py` + `tests/test_review_finalize.py`: green
      success-run + current-head tick, red-run hold, stale-head hold, current-`live=` green, non-sha
      `--rev` guards only the staleness referee, and `with_live_head` twin attachment. The fake `gh`
      fixtures now also answer `gh run view` so the live re-check runs hermeticly.
- [x] 5. The 11 measured red-run/stale ticks (#2296×3, #2181×6, #2061×1, #1558×1) — four cited runs
      all concluded `failure` at `e34cfd2e`, all heads stale — are recorded explicitly as stale in
      `docs/BOTS.md`, and now hold fut iterations of those closes via `tick-red-run`/`tick-stale-head`.
- [x] 6. Change-note pair (agent-wiki + docs/changes.d fragment + CHANGES.md row) documenting the
      #2288 class resolved.
- [x] 7. Validate: `make test-unit` (hermetic, no `~/bin`/`~/models` needed), `make lint`,
      `make check-wiring`, `make check-docs`, `make openspec-tasks-check`.
