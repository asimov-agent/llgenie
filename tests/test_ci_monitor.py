"""tests for scripts/ci_monitor.py (issue #3013).

Every snapshot shape is proven against a recorded payload through the injected fetch seam — zero
network, zero gh. Byte-stability is asserted on the raw stdout string, exactly what the Hermes
monitor cron hashes to decide whether an agent run is warranted.
"""
from __future__ import annotations

import pathlib
from datetime import datetime, timedelta, timezone

import pytest

import scripts.ci_monitor as ci_monitor


class FakeFetch:
    """Recorded payloads in; no gh subprocess is ever spawned."""

    def __init__(self, main_runs, open_prs, checks_by_pr, raise_error=None, head_runs=None,
                 jobs_by_run=None):
        self._main_runs = main_runs
        self._open_prs = open_prs
        self._checks_by_pr = checks_by_pr
        self._raise_error = raise_error
        self._head_runs = head_runs or {}
        self._jobs_by_run = jobs_by_run or {}

    def main_runs(self):
        if self._raise_error:
            raise self._raise_error
        return self._main_runs

    def open_prs(self):
        return self._open_prs

    def pr_checks(self, pr_number):
        return self._checks_by_pr.get(pr_number, [])

    def runs_on_head(self, head_sha):
        return self._head_runs.get(head_sha, [])

    def failing_jobs_for_run(self, run_id):
        return self._jobs_by_run.get(int(run_id), [])


MAIN_RUNS = [
    {"databaseId": 45010151478, "workflowName": "CI", "headBranch": "main", "event": "push",
     "status": "completed", "conclusion": "failure"},
    {"databaseId": 45010200001, "workflowName": "registry-liveness", "headBranch": "main",
     "event": "schedule", "status": "completed", "conclusion": "success"},
    {"databaseId": 45010200002, "workflowName": "all-pipelines", "headBranch": "main",
     "event": "schedule", "status": "completed", "conclusion": "skipped"},
    {"databaseId": 45010200003, "workflowName": "CI", "headBranch": "feat/some-lane",
     "event": "pull_request", "status": "completed", "conclusion": "success"},
    {"databaseId": 45010200004, "workflowName": "ci-hf-live", "headBranch": "main",
     "event": "schedule", "status": "in_progress", "conclusion": ""},
    {"databaseId": 45010200005, "workflowName": "engine-bump", "headBranch": "main",
     "event": "schedule", "status": "completed", "conclusion": "timed_out"},
]

OPEN_PRS = [
    {"number": 3012, "headRefOid": "8c1def4f8aaaa111111111111111111111111111",
     "headRefName": "feat/demo-3012",
     "mergeStateStatus": "CLEAN", "reviewDecision": "APPROVED", "isDraft": False},
    {"number": 3011, "headRefOid": "901838c14bbbb222222222222222222222222222",
     "headRefName": "chore/engine-bump-ollama",
     "mergeStateStatus": "BEHIND", "reviewDecision": "REVIEW_REQUIRED", "isDraft": False},
    {"number": 3013, "headRefOid": "11d99160fcccc333333333333333333333333333",
     "headRefName": "feat/demo-3013",
     "mergeStateStatus": "DIRTY", "reviewDecision": "CHANGES_REQUESTED", "isDraft": False},
    {"number": 2999, "headRefOid": "786239627dddd444444444444444444444444444",
     "headRefName": "feat/demo-2999",
     "mergeStateStatus": "CLEAN", "reviewDecision": "APPROVED", "isDraft": True},
]

CHECKS_BY_PR = {
    3012: [{"name": "ci-unit", "bucket": "pass"}, {"name": "guard", "bucket": "pass"},
           {"name": "lane A / step", "bucket": "fail"}, {"name": "lane B", "bucket": "fail"}],
    3011: [{"name": "ci-unit", "bucket": "pass"}],
    3013: [{"name": "ci-unit", "bucket": "pending"}],
    2999: [{"name": "ci-unit", "bucket": "fail"}],
}


def _snapshot(fetch):
    return ci_monitor.build_snapshot(fetch)


def test_main_red_line():
    fetch = FakeFetch(MAIN_RUNS, [], {})
    out = _snapshot(fetch)
    assert "MAIN-RED run=45010151478 workflow=CI conclusion=failure" in out
    assert "MAIN-RED run=45010200005 workflow=engine-bump conclusion=timed_out" in out
    # green, skipped, in-flight, and non-main runs produce no lines
    assert "45010200001" not in out
    assert "45010200002" not in out
    assert "45010200003" not in out
    assert "45010200004" not in out


def test_pr_incident_lines():
    fetch = FakeFetch([], OPEN_PRS, CHECKS_BY_PR)
    out = _snapshot(fetch)
    assert "PR-CHECKS pr=3012 head=8c1def4f8 failed=2" in out
    assert "PR-MERGE pr=3011 head=901838c14 merge=BEHIND" in out
    assert "PR-MERGE pr=3013 head=11d99160f merge=DIRTY" in out
    assert "PR-REVIEW pr=3013 head=11d99160f decision=CHANGES_REQUESTED" in out
    # the fully green CLEAN PR and the draft PR produce no lines
    assert "pr=2999" not in out
    assert "pending" not in out  # pending buckets are not failures


def test_clean_board_and_stability():
    clean_runs = [dict(r, conclusion="success", status="completed") for r in MAIN_RUNS]
    clean_prs = [dict(p, mergeStateStatus="CLEAN", reviewDecision="APPROVED", isDraft=False)
                 for p in OPEN_PRS]
    clean_checks = {n: [{"name": "ci-unit", "bucket": "pass"}] for n in CHECKS_BY_PR}
    fetch = lambda: FakeFetch(clean_runs, clean_prs, clean_checks)  # noqa: E731
    first = _snapshot(fetch())
    second = _snapshot(fetch())
    assert first == "MONITOR-OK"
    assert first == second  # byte-identical across identical payloads


def test_fetch_failure_line(capsys, monkeypatch):
    monkeypatch.setattr(
        ci_monitor, "Fetch",
        lambda **kw: FakeFetch([], [], {}, raise_error=RuntimeError("boom")),
    )
    rc = ci_monitor.main([])
    captured = capsys.readouterr()
    assert rc == 0
    assert captured.out.strip() == "MONITOR-ERROR gh-fetch-failed"
    assert "boom" not in captured.out  # detail belongs to stderr only, stdout stays stable
    assert "boom" in captured.err


def test_old_red_runs_age_out_of_the_window():
    now = datetime(2026, 11, 22, 12, 0, 0, tzinfo=timezone.utc)
    red = MAIN_RUNS[0]
    # three DIFFERENT workflows: the age window is its own rule, independent of supersession
    stale = dict(red, workflowName="aged-lane", updatedAt="2026-11-15T00:00:00Z")   # 7 days old
    fresh = dict(red, workflowName="fresh-lane", updatedAt="2026-11-22T11:00:00Z")   # 1 hour old
    no_stamp = dict(red, workflowName="unstamped-lane")  # recorded probe data: never aged
    lines = ci_monitor.snapshot_lines([stale, fresh, no_stamp], [], {}, now=now, max_age_hours=72)
    assert len(lines) == 2
    assert sum(f"workflow={r['workflowName']}" in line for r, line in zip([fresh, no_stamp], lines)) == 2
    assert "workflow=aged-lane" not in " ".join(lines)


def test_snapshot_lines_sorted_deterministically():
    lines = ci_monitor.snapshot_lines(MAIN_RUNS, OPEN_PRS, CHECKS_BY_PR)
    assert lines == sorted(lines)
    assert lines == ci_monitor.snapshot_lines(MAIN_RUNS, OPEN_PRS, CHECKS_BY_PR)


def test_monitor_is_read_only_no_mutation_verbs():
    """The monitor never starts, reruns, cancels, or dispatches a pipeline (AGENTS: no queue-pumping)."""
    src = pathlib.Path(ci_monitor.__file__).read_text(encoding="utf-8")
    for forbidden in ("gh run rerun", "workflow_dispatch", "gh run cancel", "gh pr merge"):
        assert forbidden not in src


# ---------------------------------------------------------------------------
# --triage (issue #3019): the snapshot is routed to the reactor, file-only
# ---------------------------------------------------------------------------
HEAD_RUNS = {
    # the recorded answer of the REAL seam (test_runs_on_head_returns… proves it is UNFILTERED):
    # the head accumulates its whole CI history, and the routing plan is what picks a representative
    OPEN_PRS[0]["headRefOid"]: [
        {"databaseId": 45019000001, "workflowName": "CI", "status": "completed", "conclusion": "failure",
         "updatedAt": "2026-11-24T10:00:00Z"},
        # the same head, the same workflow, the same failing step class: history, not a second incident
        {"databaseId": 45019000002, "workflowName": "CI", "status": "completed", "conclusion": "failure",
         "updatedAt": "2026-11-23T10:00:00Z"},
        {"databaseId": 45019000003, "workflowName": "CI", "status": "completed", "conclusion": "success",
         "updatedAt": "2026-11-24T12:00:00Z"},
    ],
}
HEAD_JOBS = {
    45019000001: ["lane A / step"],
    45019000002: ["lane A / step"],
}


def _freeze_monitor_clock(monkeypatch, now: datetime) -> None:
    """Pin the clock `ci_monitor.main` reads (line 508: `datetime.now(timezone.utc)`).

    Production ageing is untouched: only `ci_monitor`'s own module namespace is patched, so a
    real monitor tick still ages runs against the wall clock (issue #3081). `fromisoformat`
    is inherited, so `_aged_out` keeps parsing stamps normally.
    """
    class FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return now if tz is not None else now.replace(tzinfo=None)

    monkeypatch.setattr(ci_monitor, "datetime", FrozenDatetime)


def _head_runs_at(now: datetime) -> dict:
    """The recorded head runs re-stamped relative to the frozen clock, ages intact.

    Representative 24h old, same-bucket history 48h old, green run 22h old -- all inside the
    72h window. The fixture's *relative* ages are what the assertion describes, never the
    real wall clock (issue #3081).
    """
    head = OPEN_PRS[0]["headRefOid"]
    stamp = lambda hours: (now - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")  # noqa: E731
    return {head: [dict(run, updatedAt=stamp(hours))
                   for run, hours in zip(HEAD_RUNS[head], (24, 48, 22))]}


def _fake_route(routed):
    def fake_route(repo, run_id, check="make ci-unit", dry=False, file_only=False):
        routed.append((repo, run_id, dry, file_only))
        return 0
    return fake_route


@pytest.mark.parametrize("now", [
    datetime(2026, 11, 26, 9, 0, 0, tzinfo=timezone.utc),   # before the original 72h fuse
    datetime(2026, 11, 28, 12, 0, 0, tzinfo=timezone.utc),  # past 2026-11-27T10:00Z
])
def test_triage_routes_main_red_and_pr_check_incidents(capsys, monkeypatch, now):
    """The routing verdict is byte-identical on both sides of the old fixture fuse (#3081)."""
    _freeze_monitor_clock(monkeypatch, now)
    routed = []
    monkeypatch.setattr(ci_monitor.run_failure_reactor, "route", _fake_route(routed))
    monkeypatch.setattr(
        ci_monitor, "Fetch",
        lambda **kw: FakeFetch(MAIN_RUNS, OPEN_PRS, CHECKS_BY_PR, head_runs=_head_runs_at(now),
                               jobs_by_run=HEAD_JOBS),
    )
    rc = ci_monitor.main(["--triage"])
    out = capsys.readouterr().out
    assert rc == 0
    # the snapshot prints first, byte-identical to the plain monitor output
    assert "MAIN-RED run=45010151478 workflow=CI conclusion=failure" in out
    assert "MAIN-RED run=45010200005 workflow=engine-bump conclusion=timed_out" in out
    assert "PR-CHECKS pr=3012 head=8c1def4f8 failed=2" in out
    # every MAIN-RED run routes; the PR incident routes the NEWEST representative only
    assert "TRIAGE-MAIN run=45010151478 routed rc=0" in out
    assert "TRIAGE-MAIN run=45010200005 routed rc=0" in out
    assert ("TRIAGE-PR pr=3012 run=45019000001 workflow=CI owner=feat/demo-3012 "
            "classes=lane A / step routed rc=0") in out
    assert "run=45019000002" not in out  # same failing bucket: deduped away (issue #3047)
    assert "run=45019000003" not in out  # green: never routed
    # the dedupe is visible, not silent, and names the bucket nothing explained
    assert "PR-ROUTE pr=3012 head=8c1def4f8 routed=1 suppressed=1 aged=0 uncovered=lane B" in out
    # every routing is file-only, none is dry
    assert routed and all(call[3] is True for call in routed), routed
    assert all(call[2] is False for call in routed), routed
    assert {c[1] for c in routed} == {45010151478, 45010200005, 45019000001}


def test_triage_dry_previews_and_files_nothing(capsys, monkeypatch):
    routed = []
    monkeypatch.setattr(ci_monitor.run_failure_reactor, "route", _fake_route(routed))
    monkeypatch.setattr(
        ci_monitor, "Fetch",
        lambda **kw: FakeFetch(MAIN_RUNS, OPEN_PRS, CHECKS_BY_PR, head_runs=HEAD_RUNS),
    )
    rc = ci_monitor.main(["--triage", "--dry"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "TRIAGE-MAIN run=45010151478 routed rc=0" in out
    assert routed and all(call[2] is True for call in routed), routed


def test_triage_clean_board_routes_nothing(capsys, monkeypatch):
    routed = []
    monkeypatch.setattr(ci_monitor.run_failure_reactor, "route", _fake_route(routed))
    clean_runs = [dict(r, conclusion="success", status="completed") for r in MAIN_RUNS]
    clean_prs = [dict(p, mergeStateStatus="CLEAN", reviewDecision="APPROVED", isDraft=False)
                 for p in OPEN_PRS]
    clean_checks = {n: [{"name": "ci-unit", "bucket": "pass"}] for n in CHECKS_BY_PR}
    monkeypatch.setattr(ci_monitor, "Fetch",
                        lambda **kw: FakeFetch(clean_runs, clean_prs, clean_checks))
    rc = ci_monitor.main(["--triage"])
    assert rc == 0
    assert capsys.readouterr().out.strip() == "MONITOR-OK"
    assert routed == []


def test_triage_pr_incident_without_a_completed_failed_run_says_so(capsys, monkeypatch):
    routed = []
    monkeypatch.setattr(ci_monitor.run_failure_reactor, "route", _fake_route(routed))
    monkeypatch.setattr(
        ci_monitor, "Fetch",
        lambda **kw: FakeFetch([], OPEN_PRS, CHECKS_BY_PR, head_runs={}),
    )
    rc = ci_monitor.main(["--triage"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "PR-CHECKS pr=3012 head=8c1def4f8 failed=2" in out
    assert "TRIAGE-PR pr=3012 head=8c1def4f8 no-completed-failed-run found" in out
    assert routed == []


def test_runs_on_head_returns_every_run_recorded_at_the_head(monkeypatch):
    """One head read, no filter: which rows are incidents is the routing plan's job (issue #3047)."""
    seen = {}
    def fake_run_checked(argv, timeout=None):
        seen["argv"] = list(argv)
        return __import__("json").dumps([
            {"databaseId": 1, "workflowName": "CI", "status": "completed", "conclusion": "failure"},
            {"databaseId": 2, "workflowName": "CI", "status": "completed", "conclusion": "success"},
            {"databaseId": 3, "workflowName": "CI", "status": "in_progress", "conclusion": ""},
            {"databaseId": 4, "workflowName": "CI", "status": "completed", "conclusion": "timed_out"},
        ])
    monkeypatch.setattr(ci_monitor, "run_checked", fake_run_checked)
    fetch = ci_monitor.Fetch(repo="asimov-agent/llgenie")
    got = fetch.runs_on_head("abcdef1234567890")
    assert seen["argv"][:5] == ["gh", "run", "list", "--repo", "asimov-agent/llgenie"]
    assert "-c" in seen["argv"] and "abcdef1234567890" in seen["argv"]
    # every row, with its status: the plan needs to see the in-flight run to hand the PR over
    assert [r["databaseId"] for r in got] == [1, 2, 3, 4]
    assert "status" in seen["argv"][-1].split(",")


def test_the_queued_alarm_lane_own_run_is_never_routed(monkeypatch):
    seen = {}
    def fake_run_checked(argv, timeout=None):
        seen.setdefault("calls", []).append(list(argv))
        if argv[:3] == ["gh", "run", "list"]:
            return __import__("json").dumps([
                {"databaseId": 7, "workflowName": "CI", "status": "queued", "conclusion": ""},
            ])
        raise AssertionError(f"routing a queued head must not read jobs: {argv}")
    monkeypatch.setattr(ci_monitor, "run_checked", fake_run_checked)
    fetch = ci_monitor.Fetch(repo="asimov-agent/llgenie")
    plan = ci_monitor.pr_head_routing_plan(
        fetch.runs_on_head("f" * 40), ["ci-unit"], fetch.failing_jobs_for_run,
    )
    assert plan["queued"] == [7]
    assert plan["plan"] == []


# ---------------------------------------------------------------------------
# routing cost (issue #3047): a representative per (PR, workflow, failing class)
# ---------------------------------------------------------------------------
NOW = datetime(2026, 11, 24, 12, 0, 0, tzinfo=timezone.utc)


def _plan(runs, classes_by_run, buckets=("linux / unit",), **kw):
    return ci_monitor.pr_head_routing_plan(
        runs, list(buckets), lambda rid: classes_by_run.get(rid, []),
        now=kw.get("now", NOW), max_age_hours=kw.get("max_age_hours", 72),
        max_runs_per_workflow=kw.get("max_runs_per_workflow", 3),
    )


def _run(rid, workflow, conclusion="failure", status="completed", updated="2026-11-24T10:00:00Z"):
    return {"databaseId": rid, "workflowName": workflow, "status": status,
            "conclusion": conclusion, "updatedAt": updated}


def test_two_history_runs_of_the_same_workflow_and_class_route_one_representative():
    runs = [
        _run(11, "CI", updated="2026-11-24T10:00:00Z"),
        _run(12, "CI", updated="2026-11-23T10:00:00Z"),
        _run(13, "CI", updated="2026-11-22T10:00:00Z"),
    ]
    plan = _plan(runs, {11: ["linux / unit"], 12: ["linux / unit"], 13: ["linux / unit"]})
    assert [item["run"] for item in plan["plan"]] == [11]  # the NEWEST red stands for the bucket
    assert plan["plan"][0]["classes"] == ["linux / unit"]
    assert plan["suppressed"] == 2 and plan["aged"] == 0 and plan["queued"] == []
    assert plan["uncovered"] == []


def test_a_older_run_with_a_different_failing_class_still_routes():
    runs = [
        _run(11, "CI", updated="2026-11-24T10:00:00Z"),
        _run(12, "CI", updated="2026-11-23T10:00:00Z"),
    ]
    plan = _plan(runs, {11: ["linux / unit"], 12: ["linux / lint"]},
                 buckets=("linux / unit", "linux / lint"))
    assert [item["run"] for item in plan["plan"]] == [11, 12]  # coverage, not history
    assert plan["suppressed"] == 0 and plan["uncovered"] == []


def test_a_head_with_two_red_workflows_routes_one_representative_each():
    runs = [
        _run(21, "CI", updated="2026-11-24T10:00:00Z"),
        _run(22, "CI", updated="2026-11-23T09:00:00Z"),
        _run(23, "Engine Build Trigger", updated="2026-11-24T11:00:00Z"),
        _run(24, "Engine Build Trigger", updated="2026-11-23T08:00:00Z"),
    ]
    plan = _plan(runs, {21: ["unit"], 22: ["unit"], 23: ["docker build"], 24: ["docker build"]},
                 buckets=("linux / unit", "engine build trigger"))
    assert sorted((item["run"], item["workflow"]) for item in plan["plan"]) == [
        (21, "CI"), (23, "Engine Build Trigger"),
    ]
    assert plan["suppressed"] == 2 and plan["uncovered"] == []


def test_reads_per_workflow_are_capped_so_a_deep_history_cannot_grow_the_tick():
    runs = [_run(30 + i, "CI", updated=f"2026-11-24T0{i}:00:00Z") for i in range(1, 6)]
    # five reds of one workflow, each with its own failing class: the cap is three reads, newest first
    plan = _plan(runs, {31: ["a"], 32: ["b"], 33: ["c"], 34: ["d"], 35: ["e"]},
                 buckets=("a", "b", "c", "d", "e"))
    assert [item["run"] for item in plan["plan"]] == [35, 34, 33]
    assert plan["aged"] == 0
    assert plan["suppressed"] == 2  # the two reds deeper than the cap were never read
    assert plan["uncovered"] == ["a", "b"]  # named, not silently dropped
    assert ci_monitor.MAX_RUNS_PER_WORKFLOW == 3


def test_an_aged_out_failed_run_is_not_routed_and_is_counted_as_aged():
    runs = [
        _run(41, "CI", updated="2026-11-24T10:00:00Z"),
        _run(42, "CI", updated="2026-11-10T10:00:00Z"),  # 14 days old at NOW
    ]
    plan = _plan(runs, {41: ["unit"], 42: ["lint"]}, buckets=("unit", "lint"))
    assert [item["run"] for item in plan["plan"]] == [41]
    assert plan["aged"] == 1 and plan["suppressed"] == 0
    assert plan["uncovered"] == ["lint"]  # the bucket only an aged run explained


def test_a_red_run_that_explains_no_failing_bucket_is_suppressed_not_routed():
    """The measured #3047 shape: a head whose failing buckets are CI job names carried four
    `engine-build` red runs that explained none of them. The plan routes the CI representative and
    suppresses the rest instead of spending a reactor call on each."""
    runs = [
        _run(51, "CI", updated="2026-11-24T10:00:00Z"),
        _run(52, "engine-build", updated="2026-11-24T11:00:00Z"),
        _run(53, "engine-build", updated="2026-11-23T11:00:00Z"),
    ]
    plan = _plan(runs, {51: ["linux / unit"], 52: ["ollama / cuda"], 53: ["ollama / cuda"]},
                 buckets=("ci-verdict", "linux / unit", "scope", "guard"))
    assert [item["run"] for item in plan["plan"]] == [51]
    assert plan["suppressed"] == 2 and 52 not in {i["run"] for i in plan["plan"]}
    assert plan["uncovered"] == ["ci-verdict", "guard", "scope"]


def test_a_check_bucket_and_a_job_name_compare_as_the_same_key():
    """The dedupe key, not the label: `gh pr checks` buckets and the run's failing job names match
    after the workflow description and the `lane / job` prefix are normalized away (issue #3047)."""
    assert ci_monitor._check_key("linux / unit") == ci_monitor._check_key("Linux  /  Unit")
    assert ci_monitor._check_key("engine-build — builds EVERY engine (never merges)") == \
        ci_monitor._check_key("engine-build")
    assert ci_monitor._check_key("ollama / cuda") != ci_monitor._check_key("ollama / rocm")


# ---------------------------------------------------------------------------
# supersession (issue #3048): only the newest completed main run of a workflow is an incident
# ---------------------------------------------------------------------------
SUPERSEDING_MAIN_RUNS = [
    # red at run=1 …
    {"databaseId": 45020000001, "workflowName": "ci-verdict", "headBranch": "main",
     "event": "push", "status": "completed", "conclusion": "failure",
     "updatedAt": "2026-11-23T10:00:00Z"},
    # … and a newer completed main run of the SAME workflow turned green at run=2
    {"databaseId": 45020000002, "workflowName": "ci-verdict", "headBranch": "main",
     "event": "push", "status": "completed", "conclusion": "success",
     "updatedAt": "2026-11-23T14:00:00Z"},
    # a workflow that is red at its newest completed run: stays an incident, its older red is history
    {"databaseId": 45020000003, "workflowName": "security-scan", "headBranch": "main",
     "event": "schedule", "status": "completed", "conclusion": "failure",
     "updatedAt": "2026-11-22T10:00:00Z"},
    {"databaseId": 45020000004, "workflowName": "security-scan", "headBranch": "main",
     "event": "schedule", "status": "completed", "conclusion": "cancelled",
     "updatedAt": "2026-11-23T10:00:00Z"},
    # a newer run that has not completed supersedes nothing
    {"databaseId": 45020000005, "workflowName": "registry-sync", "headBranch": "main",
     "event": "schedule", "status": "completed", "conclusion": "failure",
     "updatedAt": "2026-11-23T09:00:00Z"},
    {"databaseId": 45020000006, "workflowName": "registry-sync", "headBranch": "main",
     "event": "schedule", "status": "in_progress", "conclusion": "",
     "updatedAt": "2026-11-23T12:00:00Z"},
    # a workflow that is red once, recently: an incident, nothing superseded in it
    {"databaseId": 45020000007, "workflowName": "engine-bump", "headBranch": "main",
     "event": "schedule", "status": "completed", "conclusion": "failure",
     "updatedAt": "2026-11-24T00:30:00Z"},
]


def test_a_main_red_superseded_by_a_newer_green_run_is_not_an_incident():
    incidents, superseded = ci_monitor.classify_main_runs(SUPERSEDING_MAIN_RUNS)
    assert 45020000001 not in [r["databaseId"] for r in incidents]
    assert {r["databaseId"]: r["supersededBy"] for r in superseded} == {
        45020000001: 45020000002,  # green superseded the red
        45020000003: 45020000004,  # the newest red supersedes its own workflow's older red
    }
    out = "\n".join(ci_monitor.snapshot_lines(SUPERSEDING_MAIN_RUNS, [], {}))
    assert "MAIN-RED run=45020000001" not in out
    assert "MAIN-RED run=45020000004 workflow=security-scan conclusion=cancelled" in out
    assert "MAIN-RED run=45020000005 workflow=registry-sync conclusion=failure" in out


def test_the_age_window_still_applies_to_the_newest_completed_run():
    now = datetime(2026, 11, 25, 0, 0, 0, tzinfo=timezone.utc)
    incidents, superseded = ci_monitor.classify_main_runs(
        SUPERSEDING_MAIN_RUNS, now=now, max_age_hours=36
    )
    # the newest reds of security-scan/registry-sync are 38-39 h old at this instant: aged out
    assert [r["databaseId"] for r in incidents] == [45020000007]  # engine-bump, 23.5 h old
    assert {r["databaseId"]: r["supersededBy"] for r in superseded} == {
        45020000001: 45020000002,
        45020000003: 45020000004,
    }
    assert superseded and all("supersededBy" in r for r in superseded)


def test_snapshot_is_incident_only_by_default_and_shows_history_on_request():
    default = ci_monitor.snapshot_lines(SUPERSEDING_MAIN_RUNS, [], {})
    with_history = ci_monitor.snapshot_lines(SUPERSEDING_MAIN_RUNS, [], {}, include_superseded=True)
    assert not any("MAIN-SUPERSEDED" in line for line in default)
    assert "MAIN-SUPERSEDED run=45020000001 workflow=ci-verdict conclusion=failure " \
        "superseded_by=45020000002" in with_history
    assert with_history == sorted(with_history)  # still deterministic and byte-stable
    assert with_history != default  # the knob is opt-in, so the cron gate is unaffected by default


def test_triage_never_routes_a_superseded_main_run(capsys, monkeypatch):
    routed = []
    monkeypatch.setattr(ci_monitor.run_failure_reactor, "route", _fake_route(routed))
    monkeypatch.setattr(
        ci_monitor, "Fetch",
        lambda **kw: FakeFetch(SUPERSEDING_MAIN_RUNS, [], {}),
    )
    rc = ci_monitor.main(["--triage", "--dry", "--include-superseded", "--max-age-hours", "1000000"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "MAIN-SUPERSEDED run=45020000001" in out  # shown for the human read
    assert "TRIAGE-MAIN run=45020000001" not in out  # … and never routed
    assert "TRIAGE-MAIN run=45020000002" not in out  # green: never an incident
    assert {c[1] for c in routed} == {45020000004, 45020000005, 45020000007}, routed
    assert all(call[3] is True for call in routed), routed  # file-only, as every routing is
