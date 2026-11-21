"""The stalled-job watchdog: an in_progress job past its budget is named while the run is live (issue #2992).

`gh` is stubbed on PATH so the decision logic runs against a scripted answer surface (the #1410
pattern). Measured case pinned: run 44863652918 (auto-merge trigger CI for PR #2990 head 8d4892e67)
had every job conclude within ~1 min except `linux/unit` (job 136722618230), in_progress since
03:57:56Z with updated_at frozen; the run stayed in_progress 26 minutes and the verdict/merge chain
was silent the whole window.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import scripts.stalled_job_watchdog as sjw  # via tests/conftest.py, the one import root (issue #796)

WORKFLOW = "CI"
HEAD_SHA = "8d4892e6797238fae9300fdedf26e138734d575b"


def _iso(minutes_ago: float) -> str:
    now = datetime.now(timezone.utc)
    t = now.timestamp() - minutes_ago * 60.0
    return datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _gh_stub(tmp_path: Path, monkeypatch, *, runs: list[dict], jobs_reply: dict,
             completed_runs: list[dict] | None = None,
             completed_jobs: dict | None = None,
             pulls_reply: list | None = None,
             comments_reply: list | None = None) -> Path:
    """A `gh` answering: run list (status/workflow), run view (jobs), commits/pulls,
    issues/comments, and `issue comment` (recorded to POSTS.json)."""
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    sc = tmp_path / "sc.json"
    sc.write_text(json.dumps({
        "runs": runs,
        "jobs_reply": jobs_reply,
        "completed_runs": completed_runs or [],
        "completed_jobs": completed_jobs or {},
        "pulls_reply": pulls_reply or [],
        "comments_reply": comments_reply or [],
    }))
    posts = tmp_path / "POSTS.json"
    gh = bindir / "gh"
    gh.write_text(f"""#!/usr/bin/env python3
import json, pathlib, sys
sc = json.loads(pathlib.Path({str(sc)!r}).read_text())
a = sys.argv[1:]
if a[:2] == ["run", "list"]:
    if "--status" in a:
        out = [r for r in sc["runs"] if r.get("status") == a[a.index("--status") + 1]]
    else:
        out = sc["completed_runs"]
    print(json.dumps(out)); sys.exit(0)
if a[:2] == ["run", "view"]:
    rid = a[2]
    if any(r.get("databaseId") == int(rid) for r in sc["runs"]):
        print(json.dumps(sc["jobs_reply"].get(rid, {{"jobs": []}}))); sys.exit(0)
    print(json.dumps(sc["completed_jobs"].get(rid, {{"jobs": []}}))); sys.exit(0)
if a[0] == "api":
    ep = a[1]
    if ep.endswith("/pulls"):
        print(json.dumps(sc["pulls_reply"])); sys.exit(0)
    if ep.endswith("/comments"):
        print(json.dumps(sc["comments_reply"])); sys.exit(0)
    print("unhandled api " + ep, file=sys.stderr); sys.exit(1)
if a[:2] == ["issue", "comment"]:
    body = a[a.index("--body") + 1]
    p = pathlib.Path({str(posts)!r})
    prev = json.loads(p.read_text()) if p.exists() else []
    p.write_text(json.dumps(prev + [{{"pr": a[2], "body": body}}]))
    sys.exit(0)
print("unhandled: " + " ".join(a), file=sys.stderr); sys.exit(1)
""")
    gh.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bindir}:{os.environ['PATH']}")
    return posts


def _in_progress_run(rid: int = 44863652918) -> dict:
    return {"databaseId": rid, "workflowName": WORKFLOW, "headBranch": "feat/x",
            "headSha": HEAD_SHA, "createdAt": _iso(41), "updatedAt": _iso(41),
            "url": f"https://github.com/asimov-agent/llgenie/actions/runs/{rid}",
            "status": "in_progress"}


def _jobs(stalled_min: float, unit_job_id: int = 136722618230) -> dict:
    """The measured shape: guard concluded, linux/unit still in_progress."""
    return {"jobs": [
        {"id": 1, "name": "guard", "status": "completed", "conclusion": "success",
         "startedAt": _iso(41), "completedAt": _iso(40)},
        {"id": unit_job_id, "name": "linux/unit", "status": "in_progress",
         "startedAt": _iso(stalled_min)},
    ]}


def _history(unit_walls: list[float]) -> tuple[list[dict], dict]:
    """Completed runs of the same workflow whose linux/unit wall times are `unit_walls` minutes."""
    runs, jobs = [], {}
    for i, w in enumerate(unit_walls):
        rid = 900 + i
        runs.append({"databaseId": rid, "conclusion": "success"})
        jobs[str(rid)] = {"jobs": [
            {"name": "linux/unit", "status": "completed", "conclusion": "success",
             "startedAt": _iso(100 + w), "completedAt": _iso(100)},
        ]}
    return runs, jobs


def _pulls(pr: int = 2990) -> list:
    return [{"number": pr, "state": "open", "head": {"sha": HEAD_SHA}}]


def test_a_stalled_unit_job_past_its_budget_is_flagged_once(tmp_path, monkeypatch, capsys):
    """AC1 — the measured shape: median unit wall 12 min -> budget 15 min; job stalled 40 min."""
    posts = _gh_stub(tmp_path, monkeypatch,
                     runs=[_in_progress_run()], jobs_reply={"44863652918": _jobs(40.0)},
                     completed_runs=_history([10.0, 12.0, 14.0])[0],
                     completed_jobs=_history([10.0, 12.0, 14.0])[1],
                     pulls_reply=_pulls())
    rc = sjw.main(["--repo", "asimov-agent/llgenie"])
    out = capsys.readouterr().out
    assert rc == 1, out  # finding, no --file
    assert "44863652918" in out, out
    assert "linux/unit" in out, out
    assert "40 min" in out, out


def test_a_stalled_job_gets_exactly_one_comment_on_its_pr(tmp_path, monkeypatch, capsys):
    """--file posts one deduped comment naming the job, the elapsed time and the budget."""
    posts = _gh_stub(tmp_path, monkeypatch,
                     runs=[_in_progress_run()], jobs_reply={"44863652918": _jobs(40.0)},
                     completed_runs=_history([10.0, 12.0, 14.0])[0],
                     completed_jobs=_history([10.0, 12.0, 14.0])[1],
                     pulls_reply=_pulls())
    rc = sjw.main(["--repo", "asimov-agent/llgenie", "--file"])
    out = capsys.readouterr().out
    posted = json.loads(posts.read_text())
    assert rc == 0, out
    assert len(posted) == 1, posted
    body = posted[0]["body"]
    assert posted[0]["pr"] == "2990", posted
    assert "linux/unit" in body and "40 min" in body, body
    assert "stalled-job-watchdog: run 44863652918 job 136722618230" in body, body


def test_a_job_within_its_budget_is_not_flagged(tmp_path, monkeypatch, capsys):
    """AC2 — median unit wall 20 min -> budget 25 min; the job at 20 min is not stalled."""
    posts = _gh_stub(tmp_path, monkeypatch,
                     runs=[_in_progress_run()], jobs_reply={"44863652918": _jobs(20.0)},
                     completed_runs=_history([18.0, 20.0, 22.0])[0],
                     completed_jobs=_history([18.0, 20.0, 22.0])[1],
                     pulls_reply=_pulls())
    rc = sjw.main(["--repo", "asimov-agent/llgenie", "--file"])
    out = capsys.readouterr().out
    assert rc == 0, out
    assert "no run has an in_progress job past its budget" in out, out
    assert not posts.exists()


def test_a_replay_after_the_marker_posts_no_second_comment(tmp_path, monkeypatch, capsys):
    """AC3 — the marker on the PR means the sweep is silent and posts nothing new."""
    marker = ("<!-- stalled-job-watchdog: run 44863652918 job 136722618230 -->")
    posts = _gh_stub(tmp_path, monkeypatch,
                     runs=[_in_progress_run()], jobs_reply={"44863652918": _jobs(40.0)},
                     completed_runs=_history([10.0, 12.0, 14.0])[0],
                     completed_jobs=_history([10.0, 12.0, 14.0])[1],
                     pulls_reply=_pulls(),
                     comments_reply=[{"body": "… already named …\n" + marker}])
    rc = sjw.main(["--repo", "asimov-agent/llgenie", "--file"])
    out = capsys.readouterr().out
    assert rc == 0, out
    assert "already named on PR #2990" in out, out
    assert not posts.exists(), json.loads(posts.read_text()) if posts.exists() else None


def test_a_run_without_a_concluded_sibling_is_left_to_the_other_lanes(tmp_path, monkeypatch, capsys):
    """Both jobs in_progress -> not this watchdog's finding (queued/frozen lanes own it)."""
    posts = _gh_stub(tmp_path, monkeypatch,
                     runs=[_in_progress_run()],
                     jobs_reply={"44863652918": {"jobs": [
                         {"id": 1, "name": "guard", "status": "in_progress", "startedAt": _iso(90)},
                         {"id": 2, "name": "linux/unit", "status": "in_progress", "startedAt": _iso(90)},
                     ]}},
                     completed_runs=_history([10.0])[0], completed_jobs=_history([10.0])[1],
                     pulls_reply=_pulls())
    rc = sjw.main(["--repo", "asimov-agent/llgenie", "--file"])
    out = capsys.readouterr().out
    assert rc == 0, out
    assert "no run has an in_progress job past its budget" in out, out
    assert not posts.exists()


def test_no_history_uses_the_named_fallback_budget(tmp_path, monkeypatch, capsys):
    """No completed history for the job name -> 60-min fallback: 40 min is not named, 75 is."""
    _gh_stub(tmp_path, monkeypatch, runs=[_in_progress_run(1)],
             jobs_reply={"1": _jobs(40.0)}, completed_runs=[], completed_jobs={},
             pulls_reply=_pulls())
    rc = sjw.main(["--repo", "asimov-agent/llgenie", "--file"])
    out = capsys.readouterr().out
    assert rc == 0, out

    posts = _gh_stub(tmp_path, monkeypatch,
                     runs=[_in_progress_run(2)], jobs_reply={"2": _jobs(75.0)},
                     completed_runs=[], completed_jobs={}, pulls_reply=_pulls())
    rc = sjw.main(["--repo", "asimov-agent/llgenie", "--file"])
    out = capsys.readouterr().out
    posted = json.loads(posts.read_text())
    assert rc == 0, out
    assert len(posted) == 1, posted
    assert "fallback 60 min" in posted[0]["body"], posted[0]["body"]


def test_a_run_with_no_pr_is_named_in_the_report_only(tmp_path, monkeypatch, capsys):
    """A push/schedule run has no PR: named in the report, never filed."""
    posts = _gh_stub(tmp_path, monkeypatch,
                     runs=[_in_progress_run()], jobs_reply={"44863652918": _jobs(40.0)},
                     completed_runs=_history([10.0, 12.0, 14.0])[0],
                     completed_jobs=_history([10.0, 12.0, 14.0])[1],
                     pulls_reply=[])
    rc = sjw.main(["--repo", "asimov-agent/llgenie", "--file"])
    out = capsys.readouterr().out
    assert rc == 0, out
    assert "belongs to no PR" in out, out
    assert "linux/unit" in out, out
    assert not posts.exists()
