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

    def __init__(self, main_runs, open_prs, checks_by_pr, raise_error=None):
        self._main_runs = main_runs
        self._open_prs = open_prs
        self._checks_by_pr = checks_by_pr
        self._raise_error = raise_error

    def main_runs(self):
        if self._raise_error:
            raise self._raise_error
        return self._main_runs

    def open_prs(self):
        return self._open_prs

    def pr_checks(self, pr_number):
        return self._checks_by_pr.get(pr_number, [])


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
