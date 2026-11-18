"""Tests for scripts/post_merge_live_check.py — the post-merge live verification read (issue #2900).

The read is the landing record: newest completed main run of each live battery + the
check-trend-list-matrix fingerprint. These tests drive the seams with canned gh payloads
(the gh subprocess seam itself is proven live by `make post-merge-live-check` on the host).
"""
from __future__ import annotations

import json
from pathlib import Path

from scripts import post_merge_live_check as pmc

REPO = Path(__file__).resolve().parent.parent
GREEN = {"run_id": 44213000001, "event": "schedule", "conclusion": "success"}


def _runs(monkeypatch, **by_workflow):
    def fake(repo: str, workflow: str):
        return dict(by_workflow.get(workflow, GREEN))
    monkeypatch.setattr(pmc, "newest_main_run", fake)


def _fingerprint(monkeypatch, green: bool, note: str = ""):
    monkeypatch.setattr(pmc, "_matrix_check", lambda: (green, note))


def test_the_battery_roster_is_exactly_the_two_named_live_batteries():
    # The landing duty names its batteries once; a new battery enters with its issue.
    assert pmc.BATTERIES == ("registry-liveness.yml", "ci-hf-live.yml")


def test_landing_with_both_batteries_green_and_matching_fingerprint_exits_zero(monkeypatch, capsys):
    _runs(monkeypatch, **{wf: GREEN for wf in pmc.BATTERIES})
    _fingerprint(monkeypatch, True, "[trend-list-matrix] OK tests/fixtures/trend-list-matrix.json")
    assert pmc.main([]) == 0
    out = capsys.readouterr().out
    assert "registry-liveness.yml run=44213000001 event=schedule conclusion=success green=1" in out
    assert "ci-hf-live.yml run=44213000001 event=schedule conclusion=success green=1" in out
    assert "check-trend-list-matrix green=1" in out
    assert "post-merge-live-check: OK" in out


def test_a_red_battery_on_main_exits_nonzero_and_names_the_trend_refresh_action(monkeypatch, capsys):
    _runs(monkeypatch, **{
        "registry-liveness.yml": GREEN,
        "ci-hf-live.yml": {"run_id": 44212692903, "event": "schedule", "conclusion": "failure"},
    })
    _fingerprint(monkeypatch, True)
    assert pmc.main([]) == 1
    out = capsys.readouterr().out
    assert "ci-hf-live.yml run=44212692903 event=schedule conclusion=failure green=0" in out
    assert "trend-refresh issue" in out


def test_a_battery_that_never_ran_on_main_is_red_never_a_silent_zero(monkeypatch, capsys):
    def none(repo: str, workflow: str):
        return None
    monkeypatch.setattr(pmc, "newest_main_run", none)
    _fingerprint(monkeypatch, True)
    assert pmc.main([]) == 1
    assert "never completed a run on main" in capsys.readouterr().out


def test_a_fingerprint_drift_exits_nonzero_even_with_green_batteries(monkeypatch, capsys):
    _runs(monkeypatch, **{wf: GREEN for wf in pmc.BATTERIES})
    _fingerprint(monkeypatch, False,
                 "[trend-list-matrix] DRIFT: metal/16/8 pins 13 GB, vendored trending says 9 GB")
    assert pmc.main([]) == 1
    out = capsys.readouterr().out
    assert "check-trend-list-matrix green=0 note=[trend-list-matrix] DRIFT: metal/16/8" in out
    assert "trend-refresh issue" in out


def test_an_unreadable_stream_is_exit_two_never_silent_zero(monkeypatch, capsys):
    def boom(repo: str, workflow: str):
        raise RuntimeError("gh api failed: HTTP 500")
    monkeypatch.setattr(pmc, "newest_main_run", boom)
    assert pmc.main([]) == 2
    assert "CANNOT READ" in capsys.readouterr().err


def test_json_output_carries_both_batteries_and_the_fingerprint(monkeypatch, capsys):
    _runs(monkeypatch, **{wf: GREEN for wf in pmc.BATTERIES})
    _fingerprint(monkeypatch, True)
    assert pmc.main(["--json"]) == 0
    # the verdict lines are JSON first, then the one-line human summary
    doc = json.loads(capsys.readouterr().out.splitlines()[0])
    assert [b["workflow"] for b in doc["batteries"]] == list(pmc.BATTERIES)
    assert all(b["green"] for b in doc["batteries"]) and doc["fingerprint"]["green"]


def test_the_printed_verdicts_carry_only_names_ids_events_conclusions(monkeypatch, capsys):
    _runs(monkeypatch, **{wf: GREEN for wf in pmc.BATTERIES})
    _fingerprint(monkeypatch, True)
    assert pmc.main([]) == 0
    out = capsys.readouterr().out
    for secretish in ("Authorization", "Bearer", "gh_"):
        assert secretish not in out


def test_the_landing_duty_is_recorded_in_agents_md_naming_both_batteries():
    # AGENTS.md is the durable behavior; this test is the box that keeps it there.
    agents = (REPO / "AGENTS.md").read_text()
    assert "## Post-merge live verification (MANDATORY, durable)" in agents
    duty = agents.split("## Post-merge live verification (MANDATORY, durable)", 1)[1]
    duty = duty.split("\n## ", 1)[0]
    for must_name in ("make post-merge-live-check", "registry-liveness.yml", "ci-hf-live.yml",
                      "check-trend-list-matrix", "trend-refresh issue"):
        assert must_name in duty, f"AGENTS.md landing duty no longer names {must_name}"
