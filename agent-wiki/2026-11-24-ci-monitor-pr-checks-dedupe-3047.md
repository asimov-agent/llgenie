# 2026-11-24 — PR-checks triage: a routing per failing check bucket, not per historical red run (issue #3047)

## What was verified against the issue

- The inflation was measured on the live board before and after, from the same board state. Old code
  (`make -s ci-monitor-triage DRY=1` at the pre-change `main`): **29** `TRIAGE-PR` routings for the
  eight open PRs (seven review-held engine-bump PRs #3029–#3035 plus #3058), 0 coverage lines. New
  code on the same board: **21** `TRIAGE-PR` routings and **8** `PR-ROUTE` coverage lines
  (`make -s ci-monitor-triage DRY=1`, rc=0) — the reactor is asked about 8 runs it had already seen.
- The per-PR shape is what the issue names: #3029 went **7 → 2** (`PR-ROUTE pr=3029 head=4958f3953
  routed=2 suppressed=5 aged=0`) and #3033 **4 → 2**; #3030/#3031/#3032/#3035 keep their 3–4 routings
  because their failing buckets (`ci-verdict`, `guard`, `scope`, `trigger`, `linux / unit`) genuinely
  sit on different runs — coverage, not history, now decides.
- `runs_on_head(sha)` (`gh run list -c <sha>`, with `status`) is the ONE head read the triage leg
  makes; `failed_runs_on_head` is gone, and which rows are incidents is decided on that payload by
  the pure `pr_head_routing_plan`. `failing_jobs_for_run(run_id)` (`gh run view <id> --json jobs`)
  supplies the run's failing job names as a payload, never a guess.
- `pr_head_routing_plan` routes newest-completed-red-first across the head's workflows with a per-workflow
  read cap (`MAX_RUNS_PER_WORKFLOW = 3`), and a run is routed only while it still stands for a bucket
  no already-routed run covers; `_check_key` is the normalization that makes `gh pr checks`'
  `linux / unit` and the run's job `linux / unit` the same key (`— <description>` suffix dropped,
  `lane / job` reduced to its job part, lower-cased, whitespace collapsed).
- A head whose newest run is still `queued`/`in_progress`/`waiting` is never routed and its job
  payloads are never read: the tick prints `TRIAGE-QUEUED pr=<n> head=<sha> owner=queued-alarm
  runs=<ids>` (the measured pending run `45281314211` on `chore/engine-bump-ollama` is that case).
- Every PR routing names the branch that owns the fix (`owner=<headRefName>`), because AGENTS.md fixes
  a failed PR pipeline on its own branch.
- `tests/test_ci_monitor.py` is 24 tests, rc=0, on recorded payloads only: representative routing,
  bucket-cover routing across two workflows, the read cap, the aged window, a red run that explains no
  failing bucket (the measured #3029 `engine-build` shape), `_check_key` equality, the queued-alarm
  hand-off, the unchanged `PR-CHECKS` snapshot, and the read-only invariant (no `gh run rerun`,
  `workflow_dispatch`, `gh run cancel`, `gh pr merge` in the triage source).

## Decisions

- Coverage replaced the `(workflow, class)` pair as the routing rule. The first draft routed the newest
  run per workflow and then older runs carrying an uncovered class; measured on the live board that
  only cut 27→28 of the routings, because four `engine-build` reds on #3029's head were the newest red
  of their workflow yet explained none of its failing buckets. The plan now asks the buckets first and
  treats run/workflow names as candidate keys, which is what the acceptance criterion actually claims.
- `suppressed` counts every fresh completed red on the head the plan declined (not merely the ones it
  examined), so the number a reviewer reads matches the history that stopped being routed; buckets the
  cap could not reach are named in `uncovered` instead of being silently dropped.
- The test seam moved with the code instead of keeping a compatibility wrapper: `HEAD_RUNS` is now an
  unfiltered head history (two same-class reds plus a green), `FakeFetch` gained `head_runs` and
  `jobs_by_run`, and the old assertions were re-pinned rather than duplicated.
- The main-red half of the same incident is not in this lane: it landed as `feat/ci-monitor-superseded-reds`
  (issue #3048, PR #3052).

## Agent behavior mirror

- A monitor tick routes a PR head's failing buckets, not its history; `PR-ROUTE … suppressed=… aged=…
  uncovered=…` is the line that tells a reviewer how much of the head was deliberately ignored.
- A pending head belongs to the queued-alarm lane and reads nothing.

## Current status

Branch `feat/ci-monitor-pr-checks-dedupe`, OpenSpec change `ci-monitor-pr-checks-dedupe`, issue #3047;
the routing reduction is measured live at the head and the numbers above are the ones the PR body cites.
