"""Tests for scripts/monitor_triage_sweep.py (issue #3049).

Recorded payloads in, zero network, zero gh: the fake fetch replays `main` runs and open issues, and
the write seam is a recorder. Every verdict line shape the issue names is asserted on the raw string,
and the dry/apply split is asserted on which argv lists end up populated.
"""
from __future__ import annotations

import datetime as dt
import pathlib

import scripts.ci_monitor as ci_monitor
import scripts.monitor_triage_sweep as sweep

NOW = dt.datetime(2026, 11, 24, 12, 0, 0, tzinfo=dt.timezone.utc)
REPO = "asimov-agent/llgenie"


def _issue(number: int, workflow: str, run, *, marker: bool = True, label: bool = True):
    body = "<!-- run-fixer: ci.yml/Run unit tests -->\n\n## Technical\n"
    if not marker:
        body = "## Problem\na hand-written issue with no reactor marker\n"
    # The reactor writes the Technical fields as `- ` bullets (measured on issue #3042).
    body += f"- **workflow:** `{workflow}`\n- **run:** `{run}`\n"
    labels = [{"name": sweep.PIPELINES_LABEL}] if label else [{"name": "agent:implement"}]
    return {"number": number, "title": f"run {run} failed", "body": body, "labels": labels,
            "createdAt": "2026-11-20T00:00:00Z"}


def _run(rid: int, workflow: str, conclusion: str, *, branch: str = "main",
         status: str = "completed", updated: str = "2026-11-20T00:00:00Z"):
    return {"databaseId": rid, "workflowName": workflow, "headBranch": branch, "event": "push",
            "status": status, "conclusion": conclusion, "updatedAt": updated}


class FakeFetch:
    """Recorded payloads in; no gh subprocess is ever spawned."""

    def __init__(self, main_runs, issues, comments=None):
        self._main_runs = main_runs
        self._issues = issues
        self._comments = comments or {}
        self.comment_reads = []

    def main_runs(self):
        return self._main_runs

    def open_issues(self):
        return self._issues

    def issue_comments(self, number):
        self.comment_reads.append(number)
        return self._comments.get(number, [])


def _recorder():
    sent = []
    return sweep.record_argv(sent), sent


def _no_execution(monkeypatch):
    """Prove 'sends nothing' the hard way: any execution attempt explodes the test."""
    def _boom(argv, **kwargs):
        raise AssertionError(f"dry mode must not execute: {argv[:3]}")
    monkeypatch.setattr(sweep, "run_checked", _boom)


def test_superseded_filing_closes_and_names_the_superseder(monkeypatch):
    _no_execution(monkeypatch)
    runs = [_run(1000, "ci.yml", "failure", updated="2026-11-20T00:00:00Z"),
            _run(2000, "ci.yml", "success", updated="2026-11-22T00:00:00Z")]
    emit, dry_argv = _recorder()
    res = sweep.sweep(repo=REPO, fetch=FakeFetch(runs, [_issue(101, "ci.yml", 1000)]),
                      emit=emit, now=NOW)
    assert res["lines"][0] == "SWEEP issue=101 workflow=ci.yml run=1000 superseded-by 2000"
    assert res["tally"] == "re-read=1 superseded=1 live=0 no-newer-run=0 skipped-claim=0"
    # The dry seam planned the writes and sent nothing.
    closes = [c for c in res["planned"] if c[:3] == ["gh", "issue", "close"]]
    assert closes == [["gh", "issue", "close", "101", "--repo", REPO]]
    assert dry_argv == res["planned"] and dry_argv
    assert emit is not sweep.execute                          # dry seam is never the executor
    assert emit is not sweep.execute                          # ...never the executor
    bodies = [c[-1] for c in res["planned"] if c[:3] == ["gh", "issue", "comment"]]
    assert any("bot-claim: monitor-triage" in b for b in bodies)          # claim BEFORE the action
    assert any("2000" in b and "superseded" in b for b in bodies)         # names the superseder
    assert any("bot-done: monitor-triage" in b for b in bodies)           # releases the claim


def test_apply_mode_actually_sends_the_close():
    runs = [_run(1000, "ci.yml", "failure", updated="2026-11-20T00:00:00Z"),
            _run(2000, "ci.yml", "success", updated="2026-11-22T00:00:00Z")]
    sent = []

    def fake_execute(cmd):
        sent.append(cmd)

    res = sweep.sweep(repo=REPO, fetch=FakeFetch(runs, [_issue(101, "ci.yml", 1000)]),
                      emit=fake_execute, now=NOW)
    assert [c[:3] for c in sent].count(["gh", "issue", "close"]) == 1
    assert res["counts"]["superseded"] == 1


def test_live_filing_stays_open_and_records_the_current_red(monkeypatch):
    _no_execution(monkeypatch)
    runs = [_run(1500, "registry-sync.yml", "failure", updated="2026-11-20T00:00:00Z"),
            _run(2500, "registry-sync.yml", "failure", updated="2026-11-23T00:00:00Z")]
    emit, dry_argv = _recorder()
    res = sweep.sweep(repo=REPO, fetch=FakeFetch(runs, [_issue(102, "registry-sync.yml", 1500)]),
                      emit=emit, now=NOW)
    assert res["lines"][0] == ("SWEEP issue=102 workflow=registry-sync.yml run=1500 "
                               "live newest-red=2500")
    assert res["tally"] == "re-read=1 superseded=0 live=1 no-newer-run=0 skipped-claim=0"
    assert not [c for c in res["planned"] if "close" in c]
    bodies = [c[-1] for c in res["planned"]]
    assert any("2500" in b for b in bodies)          # records the run id red now
    assert dry_argv == res["planned"] and dry_argv


def test_the_filing_that_is_still_the_newest_red_needs_no_comment():
    runs = [_run(1500, "registry-sync.yml", "failure", updated="2026-11-23T00:00:00Z")]
    emit, sent = _recorder()
    res = sweep.sweep(repo=REPO, fetch=FakeFetch(runs, [_issue(102, "registry-sync.yml", 1500)]),
                      emit=emit, now=NOW)
    assert res["lines"][0] == ("SWEEP issue=102 workflow=registry-sync.yml run=1500 "
                               "live newest-red=1500")
    assert res["planned"] == []


def test_a_live_filing_whose_comments_already_named_the_current_red_is_not_re_commented():
    """Given the newest red is 2500 and an earlier sweep pass already commented that run id on the
    issue. When the sweep runs again. Then the verdict line still reads live and the pass plans no
    write — re-running the sweep must not stack the same comment on the same issue (#3049)."""
    runs = [_run(1500, "registry-sync.yml", "failure", updated="2026-11-20T00:00:00Z"),
            _run(2500, "registry-sync.yml", "failure", updated="2026-11-23T00:00:00Z")]
    already = sweep.live_body({"workflow": "registry-sync.yml", "run": 1500}, 2500)
    fetch = FakeFetch(runs, [_issue(102, "registry-sync.yml", 1500)], comments={102: [{"body": already}]})
    emit, sent = _recorder()
    res = sweep.sweep(repo=REPO, fetch=fetch, emit=emit, now=NOW)
    assert res["lines"][0] == ("SWEEP issue=102 workflow=registry-sync.yml run=1500 "
                               "live newest-red=2500")
    assert res["planned"] == [] and sent == []


def test_no_newer_run_leaves_the_filing_open_with_no_write():
    runs = [_run(900, "ci.yml", "success", updated="2026-11-25T00:00:00Z")]  # no engine-bump run
    emit, sent = _recorder()
    res = sweep.sweep(repo=REPO, fetch=FakeFetch(runs, [_issue(103, "engine-bump.yml", 1700)]),
                      emit=emit, now=NOW)
    assert res["lines"][0] == "SWEEP issue=103 workflow=engine-bump.yml run=1700 no-newer-run"
    assert res["tally"] == "re-read=1 superseded=0 live=0 no-newer-run=1 skipped-claim=0"
    assert res["planned"] == []
    assert sent == []


def test_a_live_claim_by_another_bot_is_skipped_and_counted():
    claim = {"createdAt": (NOW - dt.timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ"),
             "body": sweep.bot_claims.claim_comment("fix-bot", "fix",
                                                    NOW - dt.timedelta(minutes=5), run_id=777)}
    runs = [_run(1000, "ci.yml", "failure", updated="2026-11-20T00:00:00Z"),
            _run(2000, "ci.yml", "success", updated="2026-11-22T00:00:00Z")]
    emit, sent = _recorder()
    fetch = FakeFetch(runs, [_issue(104, "ci.yml", 1000)], comments={104: [claim]})
    res = sweep.sweep(repo=REPO, fetch=fetch, emit=emit, now=NOW)
    assert res["lines"][0].endswith("skipped-claim occupant=fix-bot")
    assert res["tally"] == "re-read=0 superseded=0 live=0 no-newer-run=0 skipped-claim=1"
    assert res["planned"] == []


def test_only_reactor_filings_are_swept():  # the filing marker is the candidacy key
    issues = [_issue(110, "ci.yml", 1000, marker=False),        # no filing marker
              _issue(111, "ci.yml", 1000, label=False),        # marker, no lane label: the #3044 shape
              _issue(112, "ci.yml", 1000)]
    runs = [_run(1000, "ci.yml", "failure"), _run(2000, "ci.yml", "success",
                                                  updated="2026-11-22T00:00:00Z")]
    emit, _sent = _recorder()
    fetch = FakeFetch(runs, issues)
    res = sweep.sweep(repo=REPO, fetch=fetch, emit=emit, now=NOW)
    assert [v["number"] for v in res["verdicts"]] == [111, 112]   # the marker decides candidacy
    assert [v["pipelines_lane"] for v in res["verdicts"]] == [False, True]
    assert fetch.comment_reads == [111, 112]                   # no claim read for a non-filing


def test_dry_run_carries_no_pipeline_mutation_in_any_argv(monkeypatch):
    _no_execution(monkeypatch)
    runs = [_run(1000, "ci.yml", "failure"), _run(2000, "ci.yml", "success",
                                                  updated="2026-11-22T00:00:00Z"),
            _run(1500, "registry-sync.yml", "failure"),
            _run(2500, "registry-sync.yml", "failure", updated="2026-11-23T00:00:00Z")]
    issues = [_issue(101, "ci.yml", 1000), _issue(102, "registry-sync.yml", 1500),
              _issue(103, "engine-bump.yml", 1700)]
    emit, dry_argv = _recorder()
    res = sweep.sweep(repo=REPO, fetch=FakeFetch(runs, issues), emit=emit, now=NOW)
    flat = " ".join(" ".join(c) for c in res["planned"])
    for forbidden in ("gh run rerun", "workflow_dispatch", "gh run cancel", "gh pr merge",
                      "gh run delete"):
        assert forbidden not in flat
    assert dry_argv == res["planned"] and dry_argv
    assert emit is not sweep.execute
    assert res["planned"]
    assert not any(c[1:3] == ["run", "rerun"] for c in res["planned"])
    assert res["tally"] == "re-read=3 superseded=1 live=1 no-newer-run=1 skipped-claim=0"


def test_the_sweep_and_the_monitor_agree_on_what_is_an_incident():
    """The sweep re-uses ci_monitor's incident rule, so the two cannot disagree (issue #3048)."""
    runs = [_run(1000, "ci.yml", "failure", updated="2026-11-20T00:00:00Z"),
            _run(2000, "ci.yml", "success", updated="2026-11-22T00:00:00Z"),
            _run(1500, "registry-sync.yml", "failure", updated="2026-11-20T00:00:00Z"),
            _run(2500, "registry-sync.yml", "failure", updated="2026-11-23T00:00:00Z")]
    incidents = {int(r["databaseId"]) for r in ci_monitor.main_red_runs(runs)}
    newest_red, superseded_by, newest_completed = sweep.live_index(runs)
    assert set(newest_red.values()) == incidents
    # classify_main_runs records every replaced red, even when the workflow is red again now;
    # the sweep's `live` verdict outranks that map, which is why 1500 reads as live below.
    assert superseded_by == {1000: 2000, 1500: 2500}
    emit, _sent = _recorder()
    res = sweep.sweep(repo=REPO, fetch=FakeFetch(runs, [_issue(101, "ci.yml", 1000)]),
                      emit=emit, now=NOW)
    assert 1000 not in incidents
    assert res["verdicts"][0]["verdict"] == "superseded"


def test_a_filing_outside_the_read_window_still_reads_as_superseded():
    """The named run fell out of the window, but the workflow has a newer completed green run."""
    runs = [_run(3000, "registry-sync.yml", "success", updated="2026-11-23T00:00:00Z")]
    emit, dry_argv = _recorder()
    res = sweep.sweep(repo=REPO, fetch=FakeFetch(runs, [_issue(105, "registry-sync.yml", 900)]),
                      emit=emit, now=NOW)
    assert res["lines"][0] == ("SWEEP issue=105 workflow=registry-sync.yml run=900 "
                               "superseded-by 3000")
    assert [c[:3] for c in res["planned"]].count(["gh", "issue", "close"]) == 1


def test_sweep_module_is_importable_and_wired():
    root = pathlib.Path(__file__).resolve().parents[1]
    assert (root / "scripts" / "monitor_triage_sweep.py").exists()
    mk = (root / "mk" / "bots.mk").read_text()
    assert "monitor-triage-sweep:" in mk
    assert "scripts/monitor_triage_sweep.py" in mk
