# Spec delta: host-ci-monitor (issue #3047)

## ADDED Requirements

### Requirement: the PR-checks triage leg routes a representative per failing check bucket

`scripts/ci_monitor.py`'s triage leg MUST route, for each open PR with failing checks, the failed
runs that stand for a failing check bucket on that PR's current head — one representative per bucket
— rather than every completed failed run ever recorded on that head. Candidates MUST be ordered
newest-completed-red-first across the head's workflows, the number of run reads per workflow MUST be
capped so one tick cannot expand with the head's history, and a candidate MUST be routed only while it
still stands for a bucket no already-routed run covers. A run's failing job names and its workflow
name MUST be compared to the failing bucket names through one normalized key
(`scripts/ci_monitor.py::_check_key`: lower-cased, whitespace collapsed, the workflow's `— <description>`
suffix dropped, a `lane / job` name reduced to its job part), because `gh pr checks` reports
`linux / unit` while the run reports the job `linux / unit` and the workflow
`CI — unit tests, gates, and the image pins`. Runs examined but not routed MUST be printed as
`suppressed=<count>`, and buckets no completed failed run on the head explains MUST be printed as
`uncovered=<buckets>` so the coverage claim stays readable instead of silent.

#### Scenario: several historical red runs of one workflow route one representative

- **Given** a PR head carrying three completed failed runs of one workflow whose failing job names are
  the same bucket (`linux / unit`), recorded for issue #3047 as the shape of #3029–#3035
- **When** `pr_head_routing_plan` builds the plan for that head
- **Then** only the newest red is routed, `suppressed=2` is reported, and `uncovered` is empty
- **Test:** `pytest tests/test_ci_monitor.py -q` (recorded payloads, no network)

#### Scenario: a red run that explains no failing bucket is never routed

- **Given** a PR head whose failing buckets are `ci-verdict`, `linux / unit`, `scope` and `guard`, and
  two `engine-build` red runs whose failing jobs are `ollama / cuda` (the shape measured on #3029)
- **When** the routing plan is built
- **Then** the `engine-build` runs are not routed, they are counted in `suppressed`, and the buckets
  nothing explained are named in `uncovered`
- **Test:** `pytest tests/test_ci_monitor.py -q` (recorded payloads, no network)

#### Scenario: an older run that covers a bucket the newest run lacks is still routed

- **Given** one head whose newest red fails `linux / unit` and whose older red failed `linux / lint`
- **When** the routing plan is built
- **Then** both runs are routed, each naming its `classes=`, because coverage — not recency — decides
- **Test:** `pytest tests/test_ci_monitor.py -q` (recorded payloads, no network)

#### Scenario: the read cap bounds a deep head history

- **Given** a head with five completed red runs of one workflow, all inside the incident window, and
  five failing buckets
- **When** the routing plan is built
- **Then** at most `MAX_RUNS_PER_WORKFLOW` runs are examined for that workflow, the buckets the cap
  could not reach are named in `uncovered`, and the unread reds are counted in `suppressed`
- **Test:** `pytest tests/test_ci_monitor.py -q` (recorded payloads, no network)

### Requirement: a PR head that is still running belongs to the queued-alarm lane

A PR head with a run that is still `queued`, `in_progress` or `waiting` MUST NOT be routed by the
reactor leg: the monitor MUST print `TRIAGE-QUEUED pr=<n> head=<sha> owner=queued-alarm runs=<ids>`
naming the queued-alarm lane as the owner instead, and MUST NOT read that head's job payloads. The
head read MUST therefore expose run `status` (`scripts/ci_monitor.py::runs_on_head`) and it MUST stay
the single head read the triage leg makes — which rows are incidents is decided by
`pr_head_routing_plan` on that payload, not by a second, filtered read of the same head (AGENTS.md:
one command path, no second command).

#### Scenario: a pending newest run yields no routing

- **Given** an open PR whose newest run on the head is still `in_progress`
- **When** `triage_incidents` handles it
- **Then** no `TRIAGE-PR ... routed` line appears for it, the queued-alarm ownership line does, and no
  job payload is read for that head
- **Test:** `pytest tests/test_ci_monitor.py -q` (recorded payloads, no network)

### Requirement: a routed PR-lane failure names the lane that owns the fix

Every routing the monitor issues for an open PR MUST name the PR's head branch as the owning lane in
its verdict line (`owner=<headRefName>`), because AGENTS.md fixes a failed PR pipeline on its own
branch; a reviewer reading the monitor output MUST be able to tell which branch a red check belongs
to without a second query.

#### Scenario: a red engine-bump lane names its branch

- **Given** an open engine-bump PR on branch `chore/engine-bump-ollama` with failing checks
- **When** the monitor routes its representative run
- **Then** the verdict line carries `owner=chore/engine-bump-ollama` alongside `run=<id>`,
  `classes=` and `rc=`
- **Test:** `pytest tests/test_ci_monitor.py -q` (recorded payloads, no network)

### Requirement: the PR-checks snapshot stays reported while the routing shrinks

The monitor MUST report, for every open PR, the failing check buckets on its current head as
`PR-CHECKS pr=<n> head=<sha> failed=<count>` exactly as before (the snapshot is what the report
promises, independent of how many runs get routed), and MUST route incidents through
`scripts/run_failure_reactor.py::route(..., file_only=True)` only. It MUST NOT rerun, re-dispatch,
cancel or merge a pipeline, and MUST NOT dispatch a fix-bot (AGENTS.md: queue-pumping is forbidden;
the host files tracked issues and dispatches nothing).

#### Scenario: the snapshot line is unchanged by the routing change

- **Given** an open PR with failing check buckets on its head
- **When** `make -s ci-monitor` runs after the routing dedupe lands
- **Then** the `PR-CHECKS pr=<n> head=<sha> failed=<count>` line is still printed for it
- **Test:** `pytest tests/test_ci_monitor.py -q` (recorded payloads, no network)

#### Scenario: the triage leg is read-only against pipelines

- **Given** the triage leg's source
- **When** the read-only invariant test scans it
- **Then** no `workflow run`, `rerun`, `cancel`, `merge`, `dispatch` or `push` verb appears in the code
  that builds or routes PR-head incidents
- **Test:** `pytest tests/test_ci_monitor.py -q` (the read-only invariant test)
