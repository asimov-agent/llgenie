# Tasks: the PR-checks monitor leg routes representatives, not history

## 1. One head read that shows run status

- [x] `scripts/ci_monitor.py::runs_on_head(sha)` reads every run recorded at the head commit with its
      `status` (`gh run list -c <sha> --json databaseId,workflowName,status,conclusion,updatedAt`) and
      stays the ONLY head read the triage leg makes; the completed-only `failed_runs_on_head` is gone
      and which rows are incidents is decided on that payload (AGENTS.md: no second command path).
- [x] `scripts/ci_monitor.py::failing_jobs_for_run(run_id)` reads a run's failing job names through the
      injected gh seam (`gh run view <id> --json jobs`), so the class set is a payload, not a guess.

## 2. Route a representative per failing check bucket

- [x] `scripts/ci_monitor.py::_check_key(name)` normalizes a check bucket, a job name and a workflow
      name to one comparable key (lower-case, whitespace collapsed, the `— <description>` suffix
      dropped, a `lane / job` name reduced to its job part).
- [x] `scripts/ci_monitor.py::pr_head_routing_plan` (pure, no gh call of its own): order the head's
      completed red runs newest-first across workflows with a per-workflow read cap
      (`MAX_RUNS_PER_WORKFLOW = 3`), route a run only while it stands for a failing bucket no
      already-routed run covers, and report `queued`, `aged`, `suppressed` (every fresh red declined)
      and `uncovered` (buckets no completed red on the head explains).
- [x] A head with a pending/queued/waiting run yields no routing and no job read, and names the
      queued-alarm lane as its owner (`TRIAGE-QUEUED pr=<n> head=<sha> owner=queued-alarm runs=<ids>`).
- [x] `triage_incidents` emits `TRIAGE-PR pr=<n> run=<id> workflow=<wf> owner=<headRefName>
      classes=<a,b> routed rc=<rc>` per routed run plus
      `PR-ROUTE pr=<n> head=<sha> routed=<k> suppressed=<m> aged=<a>[ uncovered=<buckets>]`; a head
      with no completed red prints `no-completed-failed-run found`. The `PR-CHECKS` snapshot line is
      byte-identical to before.

## 3. Prove the routing shape on recorded payloads

- [x] `tests/test_ci_monitor.py`: a head with three historical reds of one workflow and one failing
      bucket routes the newest representative, prints `suppressed=2`, and names the owning branch.
- [x] `tests/test_ci_monitor.py`: the measured #3029 shape — a head whose buckets are
      `ci-verdict`/`linux / unit`/`scope`/`guard` and whose `engine-build` reds fail `ollama / cuda` —
      routes the CI representative, never the `engine-build` runs, and names the unexplained buckets.
- [x] `tests/test_ci_monitor.py`: a head whose newest run is still `in_progress` produces no
      `TRIAGE-PR` routing, reads no job payload, and prints the queued-alarm ownership line.
- [x] `tests/test_ci_monitor.py`: an older run that covers a bucket the newest run lacks IS routed
      (coverage, not recency), across two workflows and within the per-workflow read cap; the cap
      leaves its unreachable buckets named, and an aged run's bucket is reported uncovered.
- [x] `tests/test_ci_monitor.py`: `_check_key` equates `gh pr checks`' bucket to a run's job name and
      keeps distinct jobs distinct; `pytest tests/test_ci_monitor.py -q` exits 0, and the read-only
      invariant still holds (no mutation verb in the triage source).

## 4. Verify before the push (replayable, at the head)

- [x] `make openspec-validate NAME=ci-monitor-pr-checks-dedupe` and
      `make openspec-tasks-check` exit 0.
- [x] `make -s ci-monitor-triage DRY=1` on the open board routes fewer PR runs than the recorded
      baseline measured from the same board with the old code, and prints `PR-ROUTE` coverage lines.
- [x] `make -s ci-monitor` still prints the same `PR-CHECKS` snapshot lines it printed before.
- [x] Fast unit gates (`make lint`, `make check-wiring`, `make check-docs`, `make check-import-roots`)
      and the full unit battery (`make test-unit`) exit 0 at the pushed head.
