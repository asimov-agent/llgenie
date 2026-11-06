"""The zero-job-pending detector: a dispatched run that never instantiates a job must be loud (issue #1410).

`queued_run_alarm` scans JOB ROWS; a run with `jobs.total_count == 0` is invisible to it and renders
"no job has been queued longer than 30 minutes" while the run stays `pending` forever. This detector
is the run-level complement. `gh` is stubbed on PATH so the decision logic runs for real against a
scripted answer surface.

Measured case pinned below: run 41321206783 (engine-build dispatch, head f41685f3) was
`pending`/`queued` with `jobs.total_count == 0` from 15:26:09Z until cancelled 15:47:45Z, and no
gate named it (#1410).
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone

from pathlib import Path

import scripts.check_zero_job_pending as czp  # via tests/conftest.py, the one import root (issue #796)


def _iso(minutes_ago: float) -> str:
    now = datetime.now(timezone.utc)
    t = now.timestamp() - minutes_ago * 60.0
    return datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _gh_stub(tmp_path: Path, runs: list[dict], jobs_total: dict[int, int], monkeypatch) -> Path:
    """A `gh` answering run list (queued+in_progress) and run view (jobs)."""
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    scenario = tmp_path / "sc.json"
    # the jobs reply uses REAL gh shape: {"jobs":[...]} with NO total_count key (measured 2026-11-06)
    jobs_reply = {str(rid): {"jobs": [{"name": f"j{n}", "status": "in_progress"} for n in range(total)]}
                  for rid, total in jobs_total.items()}
    scenario.write_text(json.dumps({"runs": runs, "jobs_reply": jobs_reply}))
    gh = bindir / "gh"
    gh.write_text(f"""#!/usr/bin/env python3
import json, pathlib, sys
sc = json.loads(pathlib.Path("{scenario}").read_text())
a = sys.argv[1:]
if a[:2] == ["run", "list"]:
    status = a[a.index("--status") + 1]
    runs = [r for r in sc["runs"] if r.get("status") == status]
    print(json.dumps(runs)); sys.exit(0)
if a[:2] == ["run", "view"]:
    print(json.dumps(sc["jobs_reply"].get(a[2], {{"jobs": []}}))); sys.exit(0)
print("unhandled: " + " ".join(a), file=sys.stderr); sys.exit(1)
""")
    gh.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bindir}:{__import__('os').environ['PATH']}")
    return gh


def _run(rid: int, status: str, minutes_ago: float = 60.0) -> dict:
    return {"databaseId": rid, "workflowName": "engine-build — builds and verifies EVERY engine",
            "headBranch": "main", "headSha": "f41685f3bd53f4811f8e7d1e6cc01d096a787e54",
            "createdAt": _iso(minutes_ago), "url": f"http://x/{rid}", "status": status}


def test_a_zero_job_run_pending_long_enough_is_flagged(tmp_path, monkeypatch, capsys):
    """The measured #1410 case: one engine-build dispatch pending 60 min with total_count==0."""
    _gh_stub(tmp_path, [_run(41321206783, "queued", 60.0)], {41321206783: 0}, monkeypatch)
    rc = czp.main(["--repo", "asimov-agent/llgenie", "--minutes", "30"])
    out = capsys.readouterr().out
    assert rc == 1, out
    assert "41321206783" in out, out
    assert "ZERO jobs" in out, out
    assert "engine-build" in out, out


def test_a_run_with_jobs_is_not_flagged(tmp_path, monkeypatch, capsys):
    """A queued run that DID instantiate jobs (the queued_run_alarm domain) is not this detector's."""
    _gh_stub(tmp_path, [_run(999, "queued", 60.0)], {999: 5}, monkeypatch)
    rc = czp.main(["--repo", "asimov-agent/llgenie", "--minutes", "30"])
    assert rc == 0, capsys.readouterr().out


def test_a_zero_job_run_behind_an_in_progress_sibling_is_not_flagged(tmp_path, monkeypatch, capsys):
    """A zero-job run QUEUED behind an in_progress sibling (the #917 serialisation case) is waiting its
    turn, not short of runners — #1704's 6/6-false-positive class must not be filed as "no runner matched".
    """
    _gh_stub(
        tmp_path,
        [
            # an in_progress sibling of the SAME (workflow, branch) holds the concurrency group —
            # itself stalled with zero jobs past threshold, so it SHOULD be flagged
            _run(41420879842, "in_progress", 60.0),
            # this later zero-job dispatch is queued behind it — waiting its turn, NOT stranded
            _run(41763202522, "queued", 60.0),
        ],
        {41420879842: 0, 41763202522: 0}, monkeypatch)
    rc = czp.main(["--repo", "asimov-agent/llgenie", "--minutes", "30"])
    out = capsys.readouterr().out
    # the queued-behind-one is EXCLUDED; only the in_progress holder itself (stalled with zero jobs) stays
    assert "41763202522" not in out, out
    assert "41420879842" in out, out


def test_a_zero_job_run_on_a_different_branch_is_not_queued_behind(tmp_path, monkeypatch, capsys):
    """The discriminator keys on (workflow, branch): an in_progress sibling on ANOTHER branch does not
    hold this run's group, so a same-workflow zero-job run on its own branch is still stranded.
    """
    r = _run(501, "queued", 60.0); r["headBranch"] = "fix/other"
    s = _run(502, "in_progress", 5.0); s["headBranch"] = "main"
    _gh_stub(tmp_path, [r, s], {501: 0, 502: 0}, monkeypatch)
    rc = czp.main(["--repo", "asimov-agent/llgenie", "--minutes", "30"])
    out = capsys.readouterr().out
    assert "run 501" in out, out  # not queued behind main's sibling → stranded on its own branch

    """A zero-job run younger than the threshold is not yet a stall."""
    _gh_stub(tmp_path, [_run(111, "in_progress", 5.0)], {111: 0}, monkeypatch)
    rc = czp.main(["--repo", "asimov-agent/llgenie", "--minutes", "30"])
    assert rc == 0


def _gh_stub_with_issues(tmp_path: Path, open_issues: list[dict], jobs_total: dict[str, int],
                         monkeypatch) -> Path:
    """A gh answering run list/view + issue list, so delivery dedupe runs for real."""
    bindir = tmp_path / "bin"; bindir.mkdir(exist_ok=True)
    scenario = tmp_path / "sc.json"
    jobs_reply = {str(rid): {"jobs": [{"name": f"j{n}", "status": "in_progress"} for n in range(total)]}
                  for rid, total in jobs_total.items()}
    scenario.write_text(json.dumps({"issues": open_issues, "jobs_reply": jobs_reply}))
    gh = bindir / "gh"
    gh.write_text(f"""#!/usr/bin/env python3
import json, pathlib, sys
sc = json.loads(pathlib.Path("{scenario}").read_text())
a = sys.argv[1:]
if a[:2] == ["run", "list"]:
    st = a[a.index("--status") + 1]
    runs = [r for r in [{{"databaseId": 7, "workflowName": "w", "headBranch": "m",
                          "headSha": "f41685f3bd53f41685f3bd53f41", "createdAt": "2026-11-01T00:00:00Z",
                          "url": "u", "status": "queued"}}] if r.get("status") == st]
    print(json.dumps(runs)); sys.exit(0)
if a[:2] == ["run", "view"]:
    print(json.dumps(sc["jobs_reply"].get(a[2], {{"jobs": []}}))); sys.exit(0)
if a[:2] == ["issue", "list"]:
    print(json.dumps(sc["issues"])); sys.exit(0)
if a[:2] == ["issue", "create"]:
    print("https://github.com/x/issues/999"); sys.exit(0)
print("UNHANDLED " + " ".join(a), file=sys.stderr); sys.exit(9)
""")
    gh.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bindir}:{__import__('os').environ['PATH']}")
    return gh


def test_file_does_not_double_report_a_run_already_flagged(tmp_path, monkeypatch):
    """--file skips a run whose open issue already carries the zero-job-pending marker (idempotent)."""
    _gh_stub_with_issues(
        tmp_path,
        [{"body": "something <!-- zero-job-pending: run 7 -->"}],
        {"7": 0}, monkeypatch)
    # render is only reached via main; call file_one_issue directly to assert the dedupe
    r = {"run": 7, "workflow": "w", "branch": "m", "head": "f41685f3bd53",
         "created": "2026-11-01T00:00:00Z", "minutes": 60.0}
    why = czp.file_one_issue("asimov-agent/llgenie", r, "body")
    assert why == "", why  # already reported → no double-file, no error


def _gh_stub_recorded(tmp_path: Path, runs: list[dict], jobs_total: dict[int, int],
                      open_issues: list[dict], monkeypatch) -> tuple[Path, Path]:
    """A `gh` answering run list/view, issue list/create AND `api .../check-runs POST`, logging each
    delivery event to events.json so the guard can assert exact POST counts."""
    bindir = tmp_path / "bin"; bindir.mkdir(exist_ok=True)
    scenario = tmp_path / "sc.json"
    jobs_reply = {str(rid): {"jobs": [{"name": f"j{n}", "status": "in_progress"} for n in range(total)]}
                  for rid, total in jobs_total.items()}
    scenario.write_text(json.dumps(
        {"runs": runs, "jobs_reply": jobs_reply, "issues": open_issues or []}))
    events = tmp_path / "events.json"
    events.write_text("[]")
    gh = bindir / "gh"
    gh.write_text(f"""#!/usr/bin/env python3
import json, pathlib, sys
sc = json.loads(pathlib.Path("{scenario}").read_text())
events = pathlib.Path("{events}")
a = sys.argv[1:]
def log(ev):
    cur = json.loads(events.read_text())
    cur.append(ev); events.write_text(json.dumps(cur))
if a[:2] == ["run", "list"]:
    st = a[a.index("--status") + 1]
    runs = [r for r in sc["runs"] if r.get("status") == st]
    print(json.dumps(runs)); sys.exit(0)
if a[:2] == ["run", "view"]:
    print(json.dumps(sc["jobs_reply"].get(a[2], {{"jobs": []}}))); sys.exit(0)
if a[:2] == ["issue", "list"]:
    print(json.dumps(sc["issues"])); sys.exit(0)
if a[:2] == ["issue", "create"]:
    log("issue_create:" + json.dumps(a)); print("https://github.com/x/issues/999"); sys.exit(0)
if a[0] == "api" and any("check-runs" in x for x in a):
    # POST head_sha is in --input file; log the check-run POST
    infile = a[a.index("--input") + 1]
    log("check_runs_post:" + pathlib.Path(infile).read_text()); sys.exit(0)
print("UNHANDLED " + " ".join(a), file=sys.stderr); sys.exit(9)
""")
    gh.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bindir}:{__import__('os').environ['PATH']}")
    return gh, events


def _events(events: Path) -> list[str]:
    return json.loads(events.read_text())


def test_stranded_zero_job_run_is_filed_once_and_forced_red(tmp_path, monkeypatch, capsys):
    """Prove-the-guard, stranded arm: a zero-job run on a FREE group is filed ONE deduped issue AND its
    head is pushed to a `ci-verdict` FAILURE check-run (conclusion=failure), so it is RED instead of an
    eternal pending. The call counts ARE the guard: exactly one issue create + exactly one check-runs POST.
    """
    gh, events = _gh_stub_recorded(
        tmp_path, [_run(41321206783, "queued", 60.0)], {41321206783: 0}, open_issues=[], monkeypatch=monkeypatch)
    rc = czp.main(["--repo", "asimov-agent/llgenie", "--minutes", "30", "--file"])
    out = capsys.readouterr().out
    assert rc == 1, out
    assert "41321206783" in out, out
    events_l = _events(events)
    issue_creates = [e for e in events_l if e.startswith("issue_create")]
    red_posts = [e for e in events_l if e.startswith("check_runs_post")]
    assert len(issue_creates) == 1, events_l      # exactly-one deduped issue
    assert len(red_posts) == 1, events_l          # exactly-one forced RED check-run
    payload = json.loads(red_posts[0].split(":", 1)[1])
    assert payload["conclusion"] == "failure", payload  # the ci-verdict RED mapping
    assert payload["head_sha"].startswith("f41685f3"), payload
    assert payload["name"] == "ci-verdict", payload


def test_queued_behind_zero_job_run_is_never_filed_or_forced_red(tmp_path, monkeypatch, capsys):
    """Prove-the-guard, benign arm: a zero-job run QUEUED behind a held group (#917 serialisation) is NOT
    the fault — --file must neither create an issue NOR post a RED check-run for it.
    """
    holder = _run(41420879842, "in_progress", 5.0)   # holds the group; short of threshold (not itself a stall)
    queued = _run(41763202522, "queued", 60.0)
    gh, events = _gh_stub_recorded(
        tmp_path, [holder, queued], {41420879842: 29, 41763202522: 0}, open_issues=[], monkeypatch=monkeypatch)
    rc = czp.main(["--repo", "asimov-agent/llgenie", "--minutes", "30", "--file"])
    out = capsys.readouterr().out
    assert rc == 0, out                              # benign — no stranded run to deliver
    assert "filed 1 deduped" not in out, out
    assert "forced 1 stranded" not in out, out
    events_l = _events(events)
    assert not any(e.startswith("issue_create") for e in events_l), events_l
    assert not any(e.startswith("check_runs_post") for e in events_l), events_l


def test_a_github_read_failure_is_exit_2(tmp_path, monkeypatch):
    """An unreadable answer is UNKNOWN, never clean (mirror the queued-runs doctrine)."""
    gh = _gh_stub(tmp_path, [], {}, monkeypatch)
    # make gh fail entirely
    gh.write_text("#!/usr/bin/env python3\nimport sys\nprint('boom', file=sys.stderr); sys.exit(1)\n")
    rc = czp.main(["--repo", "asimov-agent/llgenie"])
    assert rc == 2


def test_both_statuses_are_scanned(tmp_path, monkeypatch, capsys):
    """A zero-job run can report `queued` OR `in_progress` — scan BOTH (the queued-alarm lesson)."""
    q = _run(1, "queued", 60.0); q["headBranch"] = "main"
    i = _run(2, "in_progress", 60.0); i["headBranch"] = "fix/other"
    _gh_stub(tmp_path, [q, i], {1: 0, 2: 0}, monkeypatch)
    rc = czp.main(["--repo", "asimov-agent/llgenie", "--minutes", "30"])
    out = capsys.readouterr().out
    assert rc == 1, out  # both zero-job runs past threshold are named (distinct branches → both stranded)
    assert "run 1" in out and "run 2" in out, out
