# A pull request is not a rollout lane (#2088)

The #1859 rollout-lane half of `make check-pr-acceptance` derives an umbrella's candidate lanes from
the umbrella's OWN body citations and holds the close for any referenced number that is OPEN and
cites the umbrella back. It never asked whether that number is an issue or a pull request, and the
issues API answers `state: open` for both — so the PR that implements an umbrella registered as that
umbrella's own open lane and held its own close.

Measured on PR #1696 (run `42440654316` job `128608975606`, head `0d09448b49`, 2026-11-08T02:57:37Z):
two `rollout-lane-open` violations whose own evidence named `#1696`, the PR being checked — `#1558`'s
body cites `#1696` and `#1696` cites `#1558` back; the same held for `#1694`. The only remedy was
closing the PR, so a PR whose job is to close an umbrella could never be the thing that closes it.
The second facet: `#1694` was CLOSED at 2026-11-04T21:09:51Z (`stateReason: COMPLETED`) and a
2026-11-08 run still emitted a lane finding for it, because the gate iterated the `closes` targets
without checking that the target was still open.

## What changed

`scripts/check_pr_acceptance.py`:

- `_fetch_issue_meta` now reads `gh api repos/<repo>/issues/<n>` and returns
  `(body, state, is_pull_request)`. The REST record carries the `pull_request` key (the
  `gh issue view --json` field list has no `isPullRequest`), and a merged PR is reported as `MERGED`
  from `state: closed` + `pull_request.merged_at`. `_fetch_issue_body` is a thin wrapper on it, so
  there is one live-read seam, not two.
- `rollout_lane_findings` skips a referenced number that is a pull request, whatever its state.
- `main()`'s `check` loop reads the close target through `_fetch_issue_meta` and skips the lane
  probe when the target is already `CLOSED`/`MERGED`. `acceptance_verdict` still runs on such a
  target: a closed issue's unticked criteria are still unproven, and #2088 excludes that half.

## Verification

- Guard proof (planted control): with `scripts/check_pr_acceptance.py` restored to `origin/main`'s
  `e51f2fd0` copy and the new tests in place, `tests/test_check_pr_acceptance.py` reports
  **2 failed, 35 passed** — exactly `test_open_pull_request_citing_the_umbrella_is_not_a_lane` and
  `test_already_closed_close_target_yields_no_lane_finding`. On the fixed script: **37 passed**.
- Live differential (the only surviving live instance of the shape, measured 2026-11-08): a PR body
  closing open issue `#2094` (whose body cites open PR `#2051`, and `#2051` cites `#2094` back) —
  pre-fix `5 violation(s)` including `a referenced rollout lane of #2094 is still OPEN … #2051`;
  post-fix `4 violation(s)`, **zero** `rollout-lane` findings (the four are the out-of-scope
  unticked-criteria half of `#2094`, unchanged by this issue).

## References

- Issue #2088; the gate's own history #1792/#1859/#1815, and the measured instances #1696 → #1558,
  #1694.
- `scripts/check_pr_acceptance.py` — `_fetch_issue_meta`, `rollout_lane_findings`, `main()`.
- `openspec/changes/acceptance-gate-pr-not-a-lane/`.
