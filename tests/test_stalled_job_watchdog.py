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


def _gh_stub(tmp_path, monkeypatch, *, runs: list[dict], jobs_reply: dict,
             completed_runs: list[dict] | None = None,
             completed_jobs: dict | None = None,
             pulls_reply: list | None = None,
             comments_reply: list | None = None,
             live_reply: dict | None = None,
             cancel_reply: dict | None = None):
    """A `gh` answering: run list (status/workflow), run view (jobs; `status,jobs` for the cancel
    gate's LIVE re-read), run cancel (recorded to CANCELS.json), commits/pulls, issues/comments,
    and `issue comment` (recorded to POSTS.json). Every call lands in CALLS.json — the negative
    control reads it to prove the cancel path never reruns or dispatches anything.
    Returns (posts_path, cancels_path, calls_path)."""
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
        "live_reply": live_reply or {},
        "cancel_reply": cancel_reply,
    }))
    posts = tmp_path / "POSTS.json"
    cancels = tmp_path / "CANCELS.json"
    calls = tmp_path / "CALLS.json"
    gh = bindir / "gh"
    gh.write_text(f"""#!/usr/bin/env python3
import json, pathlib, sys
sc = json.loads(pathlib.Path({str(sc)!r}).read_text())
a = sys.argv[1:]
def _rec(path, entry):
    p = pathlib.Path(path)
    prev = json.loads(p.read_text()) if p.exists() else []
    p.write_text(json.dumps(prev + [entry]))
_rec({str(calls)!r}, a)
if a[:2] == ["run", "list"]:
    if "--status" in a:
        out = [r for r in sc["runs"] if r.get("status") == a[a.index("--status") + 1]]
    else:
        out = sc["completed_runs"]
    print(json.dumps(out)); sys.exit(0)
if a[:2] == ["run", "view"]:
    rid = a[2]
    fields = a[a.index("--json") + 1] if "--json" in a else "jobs"
    if any(r.get("databaseId") == int(rid) for r in sc["runs"]):
        if fields == "status,jobs":
            # the cancel gate's live re-read: explicit answer, else it mirrors the detection view
            live = sc["live_reply"].get(rid) or {{"status": "in_progress", **sc["jobs_reply"].get(rid, {{"jobs": []}})}}
            print(json.dumps(live)); sys.exit(0)
        print(json.dumps(sc["jobs_reply"].get(rid, {{"jobs": []}}))); sys.exit(0)
    print(json.dumps(sc["completed_jobs"].get(rid, {{"jobs": []}}))); sys.exit(0)
if a[:2] == ["run", "cancel"]:
    _rec({str(cancels)!r}, {{"run": a[2]}})
    cr = sc.get("cancel_reply") or {{"exit": 0}}
    if cr.get("exit", 0):
        print(cr.get("stderr", ""), file=sys.stderr); sys.exit(cr["exit"])
    sys.exit(0)
if a[0] == "api":
    ep = a[1]
    if ep.endswith("/pulls"):
        print(json.dumps(sc["pulls_reply"])); sys.exit(0)
    if ep.endswith("/comments"):
        print(json.dumps(sc["comments_reply"])); sys.exit(0)
    print("unhandled api " + ep, file=sys.stderr); sys.exit(1)
if a[:2] == ["issue", "comment"]:
    body = a[a.index("--body") + 1]
    _rec({str(posts)!r}, {{"pr": a[2], "body": body}})
    sys.exit(0)
print("unhandled: " + " ".join(a), file=sys.stderr); sys.exit(1)
""")
    gh.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bindir}:{os.environ['PATH']}")
    return posts, cancels, calls


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


def _pulls(pr: int = 2990, draft: bool = False, state: str = "open") -> list:
    return [{"number": pr, "state": state, "draft": draft, "head": {"sha": HEAD_SHA}}]


def test_a_stalled_unit_job_past_its_budget_is_flagged_once(tmp_path, monkeypatch, capsys):
    """AC1 — the measured shape: median unit wall 12 min -> budget 15 min; job stalled 40 min."""
    posts, _cancels, _calls = _gh_stub(tmp_path, monkeypatch,
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
    posts, _cancels, _calls = _gh_stub(tmp_path, monkeypatch,
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
    posts, _cancels, _calls = _gh_stub(tmp_path, monkeypatch,
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
    posts, _cancels, _calls = _gh_stub(tmp_path, monkeypatch,
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
    posts, _cancels, _calls = _gh_stub(tmp_path, monkeypatch,
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

    posts, _cancels, _calls = _gh_stub(tmp_path, monkeypatch,
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
    posts, _cancels, _calls = _gh_stub(tmp_path, monkeypatch,
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


# ---------------------------------------------------------------------------
# issue #2997 — the cancel policy #2992 deferred: `--cancel-stalled` (CANCEL=1)
# ---------------------------------------------------------------------------

def _cancel_scenario(tmp_path, monkeypatch, **over):
    """The measured stalled shape + a scripted cancel outcome; returns (posts, cancels, calls)."""
    kw = dict(runs=[_in_progress_run()], jobs_reply={"44863652918": _jobs(40.0)},
              completed_runs=_history([10.0, 12.0, 14.0])[0],
              completed_jobs=_history([10.0, 12.0, 14.0])[1],
              pulls_reply=_pulls())
    kw.update(over)
    return _gh_stub(tmp_path, monkeypatch, **kw)


def test_cancel_stalled_cancels_the_pr_head_run_and_the_comment_names_it(
        tmp_path, monkeypatch, capsys):
    """AC2 — cancel BEFORE filing: the classified stalled OPEN-PR run is cancelled and the single
    comment states the outcome that ACTUALLY happened (the comment carries `cancelled`)."""
    posts, cancels, _calls = _cancel_scenario(tmp_path, monkeypatch)
    rc = sjw.main(["--repo", "asimov-agent/llgenie", "--file", "--cancel-stalled"])
    out = capsys.readouterr().out
    assert rc == 0, out
    assert json.loads(cancels.read_text()) == [{"run": "44863652918"}], out
    posted = json.loads(posts.read_text())
    assert len(posted) == 1, posted
    body = posted[0]["body"]
    assert "CANCELLED" in body and "issue #2997" in body, body
    assert "never dispatches, reruns, or re-triggers" not in body or "A cancel ENDS a run" in body
    assert "STALLED-JOB CANCEL: 1 cancelled" in out, out


def test_a_run_that_concluded_between_classification_and_cancel_is_skipped(
        tmp_path, monkeypatch, capsys):
    """Proof 2 (#1822/#1823) — the LIVE re-read shows the stalled job concluded since
    classification: the cancel is SKIPPED, `gh run cancel` is never invoked, and the comment says
    why instead of pretending the wedge cleared."""
    live = {"44863652918": {"status": "completed", "jobs": _jobs(40.0)["jobs"]}}
    posts, cancels, _calls = _cancel_scenario(tmp_path, monkeypatch, live_reply=live)
    rc = sjw.main(["--repo", "asimov-agent/llgenie", "--file", "--cancel-stalled"])
    out = capsys.readouterr().out
    assert rc == 0, out
    assert "cancel SKIPPED" in out, out
    assert not cancels.exists(), json.loads(cancels.read_text())
    body = json.loads(posts.read_text())[0]["body"]
    assert "SKIPPED" in body and "already concluded" in body, body


def test_a_concluding_job_on_an_in_progress_run_is_skipped_not_cancelled(
        tmp_path, monkeypatch, capsys):
    """Proof 2 exact case: the RUN is still in_progress but the stalled JOB concluded between
    classification and cancel — a live job is never touched."""
    live = {"44863652918": {"status": "in_progress", "jobs": [
        {"id": 1, "name": "guard", "status": "completed", "conclusion": "success",
         "startedAt": _iso(41), "completedAt": _iso(40)},
        {"id": 136722618230, "name": "linux/unit", "status": "completed",
         "conclusion": "success", "startedAt": _iso(40), "completedAt": _iso(5)},
    ]}}
    posts, cancels, _calls = _cancel_scenario(tmp_path, monkeypatch, live_reply=live)
    rc = sjw.main(["--repo", "asimov-agent/llgenie", "--file", "--cancel-stalled"])
    out = capsys.readouterr().out
    assert rc == 0, out
    assert "cancel SKIPPED" in out and "concluded between classification" in out, out
    assert not cancels.exists()
    assert "SKIPPED" in json.loads(posts.read_text())[0]["body"]


def test_a_cancel_that_races_a_conclusion_is_benign(tmp_path, monkeypatch, capsys):
    """Proof 4 (#1410 precedent) — `gh run cancel` refusing a run GitHub already ended is a benign
    race, NOT a delivery failure: exit stays 0 and the comment names the race."""
    posts, cancels, _calls = _cancel_scenario(
        tmp_path, monkeypatch,
        cancel_reply={"exit": 1, "stderr": "can't cancel run 44863652918: it is completed"})
    rc = sjw.main(["--repo", "asimov-agent/llgenie", "--file", "--cancel-stalled"])
    out = capsys.readouterr().out
    assert rc == 0, out  # NOT 3: the race is benign
    assert json.loads(cancels.read_text()) == [{"run": "44863652918"}]
    assert "raced" in out, out
    assert "benign" in json.loads(posts.read_text())[0]["body"]


def test_no_pr_draft_and_closed_heads_are_never_cancelled(tmp_path, monkeypatch, capsys):
    """Proof 3 — only OPEN, NON-DRAFT PR heads are cancellable. No-PR, draft and closed heads are
    named only; `gh run cancel` is never invoked for them."""
    def _fresh():
        for name in ("POSTS.json", "CANCELS.json", "CALLS.json"):
            f = tmp_path / name
            if f.exists():
                f.unlink()

    _fresh()
    posts, cancels, _calls = _cancel_scenario(tmp_path, monkeypatch, pulls_reply=[])
    rc = sjw.main(["--repo", "asimov-agent/llgenie", "--file", "--cancel-stalled"])
    out = capsys.readouterr().out
    assert rc == 0, out
    assert "no PR head" in out and "never cancelled" in out, out
    assert not cancels.exists()
    assert not posts.exists()

    _fresh()
    _cancel_scenario(tmp_path, monkeypatch, pulls_reply=_pulls(draft=True))
    rc = sjw.main(["--repo", "asimov-agent/llgenie", "--file", "--cancel-stalled"])
    out = capsys.readouterr().out
    assert rc == 0, out
    assert "DRAFT PR #2990" in out, out
    assert not cancels.exists(), json.loads(cancels.read_text())

    _fresh()
    posts, cancels, _calls = _cancel_scenario(
        tmp_path, monkeypatch, pulls_reply=_pulls(state="closed"))
    rc = sjw.main(["--repo", "asimov-agent/llgenie", "--file", "--cancel-stalled"])
    out = capsys.readouterr().out
    assert rc == 0, out
    assert "CLOSED PR #2990" in out, out
    assert not cancels.exists(), json.loads(cancels.read_text())
    assert len(json.loads(posts.read_text())) == 1  # still NAMED on the closed PR


def test_the_cancel_path_never_dispatches_reruns_or_retriggers(tmp_path, monkeypatch, capsys):
    """AC3 negative control — after a cancel, the watchdog invokes NOTHING that starts a pipeline:
    no `run rerun`, no `workflow_dispatch`, no re-trigger of any kind. Only reads, the cancel, and
    the comment."""
    posts, cancels, calls_path = _cancel_scenario(tmp_path, monkeypatch)
    rc = sjw.main(["--repo", "asimov-agent/llgenie", "--file", "--cancel-stalled"])
    out = capsys.readouterr().out
    assert rc == 0, out
    assert json.loads(cancels.read_text()) == [{"run": "44863652918"}]
    calls = json.loads(calls_path.read_text())
    flat = [" ".join(c) for c in calls]
    banned = [c for c in flat
              if "rerun" in c or "dispatch" in c or "workflow run" in c or "pr merge" in c]
    assert not banned, flat
    assert any(c.startswith("run cancel") for c in flat), flat
