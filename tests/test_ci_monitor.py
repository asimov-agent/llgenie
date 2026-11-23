"""tests for scripts/ci_monitor.py (issue #3013).

Every snapshot shape is proven against a recorded payload through the injected fetch seam — zero
network, zero gh. Byte-stability is asserted on the raw stdout string, exactly what the Hermes
monitor cron hashes to decide whether an agent run is warranted.
"""
from __future__ import annotations

import pathlib
from datetime import datetime, timezone

import scripts.ci_monitor as ci_monitor


class FakeFetch:
    """Recorded payloads in; no gh subprocess is ever spawned."""

    def __init__(self, main_runs, open_prs, checks_by_pr, raise_error=None, head_runs=None):
        self._main_runs = main_runs
        self._open_prs = open_prs
        self._checks_by_pr = checks_by_pr
        self._raise_error = raise_error
        self._head_runs = head_runs or {}

    def main_runs(self):
        if self._raise_error:
            raise self._raise_error
        return self._main_runs

    def open_prs(self):
        return self._open_prs

    def pr_checks(self, pr_number):
        return self._checks_by_pr.get(pr_number, [])

    def failed_runs_on_head(self, head_sha):
        return self._head_runs.get(head_sha, [])


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
     "mergeStateStatus": "CLEAN", "reviewDecision": "APPROVED", "isDraft": False},
    {"number": 3011, "headRefOid": "901838c14bbbb222222222222222222222222222",
     "mergeStateStatus": "BEHIND", "reviewDecision": "REVIEW_REQUIRED", "isDraft": False},
    {"number": 3013, "headRefOid": "11d99160fcccc333333333333333333333333333",
     "mergeStateStatus": "DIRTY", "reviewDecision": "CHANGES_REQUESTED", "isDraft": False},
    {"number": 2999, "headRefOid": "786239627dddd444444444444444444444444444",
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
    stale = dict(red, updatedAt="2026-11-15T00:00:00Z")   # 7 days old
    fresh = dict(red, updatedAt="2026-11-22T11:00:00Z")   # 1 hour old
    no_stamp = dict(red)                                   # recorded probe data: never aged
    lines = ci_monitor.snapshot_lines([stale, fresh, no_stamp], [], {}, now=now, max_age_hours=72)
    assert len(lines) == 2
    assert sum(f"run={red['databaseId']}" in line for line in lines) == 2


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
    # the recorded answer of the REAL seam (test_failed_runs_on_head_filters… proves its filter):
    # only the completed incident-conclusion row at this head ever comes back
    OPEN_PRS[0]["headRefOid"]: [
        {"databaseId": 45019000001, "workflowName": "CI", "status": "completed", "conclusion": "failure"},
    ],
}


def _fake_route(routed):
    def fake_route(repo, run_id, check="make ci-unit", dry=False, file_only=False):
        routed.append((repo, run_id, dry, file_only))
        return 0
    return fake_route


def test_triage_routes_main_red_and_pr_check_incidents(capsys, monkeypatch):
    routed = []
    monkeypatch.setattr(ci_monitor.run_failure_reactor, "route", _fake_route(routed))
    monkeypatch.setattr(
        ci_monitor, "Fetch",
        lambda **kw: FakeFetch(MAIN_RUNS, OPEN_PRS, CHECKS_BY_PR, head_runs=HEAD_RUNS),
    )
    rc = ci_monitor.main(["--triage"])
    out = capsys.readouterr().out
    assert rc == 0
    # the snapshot prints first, byte-identical to the plain monitor output
    assert "MAIN-RED run=45010151478 workflow=CI conclusion=failure" in out
    assert "MAIN-RED run=45010200005 workflow=engine-bump conclusion=timed_out" in out
    assert "PR-CHECKS pr=3012 head=8c1def4f8 failed=2" in out
    # every MAIN-RED run routes, and the PR incident routes its completed FAILED head run only
    assert "TRIAGE-MAIN run=45010151478 routed rc=0" in out
    assert "TRIAGE-MAIN run=45010200005 routed rc=0" in out
    assert "TRIAGE-PR pr=3012 run=45019000001 routed rc=0" in out
    assert "run=45019000002" not in out  # in-flight: never routed
    assert "run=45019000003" not in out  # green: never routed
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


def test_failed_runs_on_head_filters_completed_incident_conclusions(monkeypatch):
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
    got = fetch.failed_runs_on_head("abcdef1234567890")
    assert seen["argv"][:5] == ["gh", "run", "list", "--repo", "asimov-agent/llgenie"]
    assert "-c" in seen["argv"] and "abcdef1234567890" in seen["argv"]
    assert [r["databaseId"] for r in got] == [1, 4]
