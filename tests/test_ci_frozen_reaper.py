"""The frozen-in-progress reaper (#1679): an old, non-advancing run is collapsed; a live one is not.

`ci-requeue.py` re-runs only cancelled runs and `run-failure-reactor.py` fires only on failure — a
run stuck `in_progress` is invisible to both and blocks the PR verdict until a human intervenes
(observed on #1671). `scripts/ci_frozen_reaper.py` is the third trigger: it only touches a run whose
`updated_at` is older than the threshold (default 90m), only on an OPEN PR, and it posts the evidence
(named owner, run id, both timestamps) to the PR thread BEFORE it cancels anything.

Driven through a fake `gh` that records argv, so the assertions are about the exact requests.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import pathlib
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import ci_frozen_reaper as fr  # noqa: E402


def _iso(minutes_ago: float, now: dt.datetime) -> str:
    return (now - dt.timedelta(minutes=minutes_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _fake_gh(tmp_path: Path, in_progress: list[dict], prs: dict[str, list[dict]]):
    """A `gh` serving `actions/runs` (in_progress), `commits/{sha}/pulls`, `issues/{n}/comments`,
    recording every cancel/rerun and comment it is given."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "inprogress.json").write_text(json.dumps(in_progress))
    (tmp_path / "prs.json").write_text(json.dumps(prs))
    log = tmp_path / "gh.log"
    gh = tmp_path / "gh"
    gh.write_text(f'''#!{sys.executable}
import json, sys, pathlib
here = pathlib.Path(__file__).parent
args = sys.argv[1:]
with open({str(log)!r}, "a") as fh:
    fh.write(json.dumps(args) + "\\n")
if args[:2] == ["run", "cancel"] or args[:2] == ["run", "rerun"]:
    print(""); sys.exit(0)
if "issues/" in args[0] and "/comments" in args[0]:
    print("{{}}"); sys.exit(0)
url = args[1] if len(args) > 1 else ""
if "commits/" in url and "/pulls" in url:
    sha = url.split("commits/")[1].split("/pulls")[0]
    print(json.dumps(json.loads((here / "prs.json").read_text()).get(sha, [])))
elif "actions/runs" in url:
    print(json.dumps({{"workflow_runs": json.loads((here / "inprogress.json").read_text())}}))
else:
    print("{{}}")
''')
    gh.chmod(0o755)
    return gh, log


def _calls(log: Path) -> list[list[str]]:
    if not log.exists():
        return []
    return [json.loads(line) for line in log.read_text().splitlines() if line.strip()]


def _run(num: int, sha: str, updated_minutes_ago: float, now: dt.datetime, started_minutes_ago: float,
         branch: str = "feat/x") -> dict:
    return {"id": num, "name": "CI", "workflow_id": 1, "head_sha": sha, "head_branch": branch,
            "status": "in_progress", "event": "pull_request",
            "updated_at": _iso(updated_minutes_ago, now),
            "run_started_at": _iso(started_minutes_ago, now),
            "created_at": _iso(started_minutes_ago, now)}


def _pr(num: int, login: str) -> dict:
    return {"number": num, "state": "open", "html_url": f"https://github.com/o/r/pull/{num}",
            "user": {"login": login}}


def test_a_frozen_run_on_an_open_pr_is_collapsed(tmp_path, monkeypatch, capsys):
    """The #1679 case: a 120m in_progress run that has not advanced in 60m, on an open PR."""
    now = dt.datetime.now(dt.timezone.utc)
    frozen = _run(111, "a" * 40, 180, now, 240)         # stale 180m, age 240m — frozen
    gh, log = _fake_gh(tmp_path, [frozen], {"a" * 40: [_pr(7, "andyholst")]})
    monkeypatch.setenv("CI_FROZEN_GH", str(gh))

    assert fr.main(["run", "--repo", "asimov-agent/llgenie"]) == 0
    allc = _calls(log)
    # evidence comment posted BEFORE the cancel, on the PR thread
    comments = [c for c in allc if any("/comments" in a for a in c)]
    cancels = [c for c in allc if c[:2] == ["run", "cancel"]]
    reruns = [c for c in allc if c[:2] == ["run", "rerun"]]
    assert len(comments) == 1 and any("issues/7/comments" in a for a in comments[0]), comments
    assert cancels == [["run", "cancel", "111", "--repo", "asimov-agent/llgenie"]], cancels
    assert reruns == [["run", "rerun", "111", "--repo", "asimov-agent/llgenie"]], reruns
    # the comment names the owner, run id, PR — evidence a human would leave
    body = next(a for c in comments for a in c if a.startswith("body="))
    assert "andyholst" in body and "run `111`" in body and "PR #7" in body, body
    out = capsys.readouterr().out
    assert "collapsed 1 frozen run(s)" in out and "left 0 alone" in out


def test_an_advancing_run_is_left_alone(tmp_path, monkeypatch, capsys):
    """A run whose updated_at is fresh is WORKING, not frozen — never cancelled (the #817 line)."""
    now = dt.datetime.now(dt.timezone.utc)
    fresh = _run(222, "b" * 40, 1, now, 120)            # stale 1m, age 120m — still advancing (fresh updated_at)
    gh, log = _fake_gh(tmp_path, [fresh], {"b" * 40: [_pr(8, "owner")]})
    monkeypatch.setenv("CI_FROZEN_GH", str(gh))

    assert fr.main(["run"]) == 0
    assert [c for c in _calls(log) if c[:2] == ["run", "cancel"]] == []
    assert "still advancing" in capsys.readouterr().out


def test_a_run_younger_than_the_grace_is_left_alone(tmp_path, monkeypatch, capsys):
    """Issue #1679 acceptance: never fires within the first 15m of a run's life."""
    now = dt.datetime.now(dt.timezone.utc)
    young = _run(333, "c" * 40, 120, now, 5)            # stale 120m BUT age 5m (< 15m grace) — untouched
    gh, log = _fake_gh(tmp_path, [young], {"c" * 40: [_pr(9, "owner")]})
    monkeypatch.setenv("CI_FROZEN_GH", str(gh))

    assert fr.main(["run"]) == 0
    assert [c for c in _calls(log) if c[:2] == ["run", "cancel"]] == []
    assert "grace" in capsys.readouterr().out


def test_a_run_with_no_open_pr_is_left_alone(tmp_path, monkeypatch, capsys):
    """A push/schedule run is not a PR verdict — never collapsed (only open PRs block votes)."""
    now = dt.datetime.now(dt.timezone.utc)
    push = _run(444, "d" * 40, 120, now, 240, branch="main")
    gh, log = _fake_gh(tmp_path, [push], {"d" * 40: []})   # commit has no PR
    monkeypatch.setenv("CI_FROZEN_GH", str(gh))

    assert fr.main(["run"]) == 0
    assert [c for c in _calls(log) if c[:2] == ["run", "cancel"]] == []
    assert "no open PR" in capsys.readouterr().out


def test_dry_re_collapses_nothing_but_prints_the_plan(tmp_path, monkeypatch, capsys):
    """`DRY=1` / `plan` is how a reader checks the reaper without touching a runner."""
    now = dt.datetime.now(dt.timezone.utc)
    frozen = _run(555, "e" * 40, 180, now, 240)
    gh, log = _fake_gh(tmp_path, [frozen], {"e" * 40: [_pr(10, "owner")]})
    monkeypatch.setenv("CI_FROZEN_GH", str(gh))

    assert fr.main(["run", "--dry"]) == 0
    out = capsys.readouterr().out
    assert "DRY would cancel" in out, out
    assert [c for c in _calls(log) if c[:2] == ["run", "cancel"]] == []


def test_only_a_run_stale_beyond_the_threshold_is_a_candidate(tmp_path, monkeypatch):
    """Mix: only the 120m-stale run is frozen; the 10m-stale and superseeded-advancing ones are not."""
    now = dt.datetime.now(dt.timezone.utc)
    runs = [_run(1, "1" * 40, 10, now, 180),             # stale 10m < 90m threshold: advancing
            _run(2, "2" * 40, 180, now, 240)]            # stale 180m >= 90m: frozen
    gh, _log = _fake_gh(tmp_path, runs, {"1" * 40: [_pr(1, "o")], "2" * 40: [_pr(2, "o")]})
    monkeypatch.setenv("CI_FROZEN_GH", str(gh))

    freezing, kept = fr.plan("asimov-agent/llgenie", fr.parse_threshold("90m"), now=now)
    assert [r["id"] for r in freezing] == [2], (freezing, kept)
    assert [r["id"] for r in kept] == [1], (freezing, kept)


def test_the_threshold_parser_refuses_garbage():
    try:
        fr.parse_threshold("2 hours")
    except SystemExit as exc:
        assert "use e.g. 90m, 2h, 1d" in str(exc)
    else:                                    # pragma: no cover - the guard this test exists for
        raise AssertionError("a malformed threshold was accepted")
    assert fr.parse_threshold("90m") == dt.timedelta(minutes=90)
    assert fr.parse_threshold("1d") == dt.timedelta(days=1)


def test_the_scheduled_reaper_wires_exactly_the_measured_target():
    """A cron that runs a copy of the logic is a schedule with no evidence; it must call `make ci-frozen-reaper`."""
    import yaml
    path = pathlib.Path(__file__).resolve().parent.parent / ".github/workflows/ci-frozen-reaper.yml"
    wf = yaml.safe_load(path.read_text())
    on = wf.get("on") or wf.get(True)
    crons = [str(slot.get("cron")) for slot in on["schedule"]]
    assert crons == ["19 */2 * * 0,2,3,4,5,6", "27 */2 * * 1"], crons  # odd, collision-free, all-day every-2h
    assert "workflow_dispatch" in on
    assert wf["concurrency"] == {"group": "ci-frozen-reaper", "cancel-in-progress": False}
    assert wf["permissions"] == {"contents": "read", "actions": "write", "pull-requests": "write"}
    steps = wf["jobs"]["reap"]["steps"]
    assert any("make ci-frozen-reaper" in (step.get("run") or "") for step in steps), steps
    for step in steps:
        if "uses" in step:
            assert re.fullmatch(r"[^@\s]+@[0-9a-f]{40}", step["uses"]), step["uses"]
