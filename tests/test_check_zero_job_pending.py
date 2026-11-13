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


def test_a_zero_job_run_younger_than_the_threshold_is_not_flagged(tmp_path, monkeypatch):
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
                      open_issues: list[dict], monkeypatch,
                      jobs_second: dict[int, int] | None = None,
                      cancel_errors: dict[int, str] | None = None,
                      issue_create_error: str | None = None) -> tuple[Path, Path]:
    """A `gh` answering run list/view, issue list/create, `run cancel` AND `api .../check-runs POST`,
    logging each delivery event to events.json so the guard can assert exact POST counts.

    `jobs_second` makes a run's SECOND `run view` (the re-read `cancel_stranded` does at the moment of
    cancelling) answer with a different job count than the first — the test seam for "a runner finally
    arrived between classification and cancel". `cancel_errors` makes `run cancel <rid>` fail with the
    given stderr (the "already completed" race arm)."""
    bindir = tmp_path / "bin"; bindir.mkdir(exist_ok=True)
    scenario = tmp_path / "sc.json"
    jobs_reply = {str(rid): {"jobs": [{"name": f"j{n}", "status": "in_progress"} for n in range(total)]}
                  for rid, total in jobs_total.items()}
    scenario.write_text(json.dumps(
        {"runs": runs, "jobs_reply": jobs_reply, "issues": open_issues or [],
         "views": {},
         "jobs_second": {str(k): v for k, v in (jobs_second or {}).items()},
         "cancel_errors": {str(k): v for k, v in (cancel_errors or {}).items()},
         "issue_create_error": issue_create_error}))
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
    views = sc.setdefault("views", {{}})
    n = views.get(a[2], 0) + 1
    views[a[2]] = n
    pathlib.Path("{scenario}").write_text(json.dumps(sc))  # each gh call is a new process: persist the counter
    if n >= 2 and a[2] in sc.get("jobs_second", {{}}):
        t = sc["jobs_second"][a[2]]
        jr = {{"jobs": [{{"name": "s" + str(i), "status": "in_progress"}} for i in range(t)]}}
        print(json.dumps(jr)); sys.exit(0)
    print(json.dumps(sc["jobs_reply"].get(a[2], {{"jobs": []}}))); sys.exit(0)
if a[:2] == ["run", "cancel"]:
    log("run_cancel:" + a[2])
    err = sc.get("cancel_errors", {{}}).get(a[2])
    if err:
        print(err, file=sys.stderr); sys.exit(1)
    print("Cancelled run " + a[2]); sys.exit(0)
if a[:2] == ["issue", "list"]:
    print(json.dumps(sc["issues"])); sys.exit(0)
if a[:2] == ["issue", "create"]:
    log("issue_create:" + json.dumps(a))
    if sc.get("issue_create_error"):
        print(sc["issue_create_error"], file=sys.stderr); sys.exit(1)
    print("https://github.com/x/issues/999"); sys.exit(0)
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


# --cancel-stranded: naming a zombie is not clearing it (issue #1410 completion, 2026-11-12).
# The already-filed dedupe guards FILING only: a run named yesterday is still a zero-job zombie
# today, GitHub never evicts it, and the queue starves live work behind it.

def test_cancel_stranded_clears_an_already_named_zombie_without_re_naming(tmp_path, monkeypatch, capsys):
    """The 2026-11-12 pattern: five runs named 08:23Z (issues #2520-#2525) were STILL `queued` with
    zero jobs at 12:19Z because every later monitor run skipped them (marker present) and nothing
    cancelled them. --cancel-stranded must CANCEL the already-named run too, while the dedupe still
    refuses to re-file it or re-post its RED check."""
    r7 = _run(7, "queued", 60.0); r7["headBranch"] = "feat/a"    # fresh stranded: named AND cleared
    r9 = _run(9, "queued", 120.0); r9["headBranch"] = "feat/b"   # named yesterday: cleared only
    gh, events = _gh_stub_recorded(
        tmp_path, [r7, r9], {7: 0, 9: 0},
        open_issues=[{"body": "named yesterday <!-- zero-job-pending: run 9 -->"}],
        monkeypatch=monkeypatch)
    rc = czp.main(["--repo", "asimov-agent/llgenie", "--minutes", "30", "--file", "--cancel-stranded"])
    out = capsys.readouterr().out
    assert rc == 1, out
    ev = _events(events)
    cancels = sorted(e.split(":", 1)[1] for e in ev if e.startswith("run_cancel"))
    assert cancels == ["7", "9"], ev                                # BOTH cleared, the named one too
    assert sum(1 for e in ev if e.startswith("issue_create")) == 1, ev    # only the unnamed run gets an issue
    assert sum(1 for e in ev if e.startswith("check_runs_post")) == 1, ev  # RED forced once, for run 7
    assert "cancelled 2 stranded" in out, out
    assert "filed 1 deduped" in out, out
    create = json.loads([e for e in ev if e.startswith("issue_create")][0].split(":", 1)[1])
    body = create[create.index("--body") + 1]
    assert "has **already been cancelled**" in body, body[:400]  # body states the real outcome


def test_cancel_skips_a_run_whose_runner_arrived_between_classification_and_cancel(tmp_path, monkeypatch, capsys):
    """The cancel safety gate: classification said stranded (zero jobs at scan); at the moment of
    cancelling the re-read finds jobs instantiated — a runner finally arrived. A LIVE run is never
    cancelled (the #1822/#1823 class); the skip is reported loudly and the run is still named."""
    r = _run(7, "queued", 60.0); r["headBranch"] = "feat/a"
    gh, events = _gh_stub_recorded(tmp_path, [r], {7: 0}, open_issues=[], monkeypatch=monkeypatch,
                                   jobs_second={7: 2})
    rc = czp.main(["--repo", "asimov-agent/llgenie", "--minutes", "30", "--file", "--cancel-stranded"])
    out = capsys.readouterr().out
    assert rc == 1, out
    ev = _events(events)
    assert not any(e.startswith("run_cancel") for e in ev), ev      # never kill a live compile
    assert "skipped 1 (jobs instantiated since classification)" in out, out
    assert "cancel skipped: run 7: 2 job(s) instantiated" in out, out
    assert sum(1 for e in ev if e.startswith("issue_create")) == 1, ev  # still named; body states the skip
    create = json.loads([e for e in ev if e.startswith("issue_create")][0].split(":", 1)[1])
    body = create[create.index("--body") + 1]
    assert "the monitor's cancel was **skipped**" in body, body[:400]


def test_cancel_stranded_never_touches_a_queued_behind_run(tmp_path, monkeypatch, capsys):
    """#1704's discriminator holds for cancelling too: a zero-job run QUEUED behind an in_progress
    sibling of the same (workflow, branch) is waiting its turn — it is neither filed nor cancelled.
    Cancel-only mode (--cancel-stranded without --file) files nothing at all."""
    holder = _run(210, "in_progress", 60.0)                  # stalled holder: stranded, cleared
    behind = _run(211, "queued", 60.0)                       # same wf+branch → waiting, never touched
    other = _run(213, "queued", 60.0); other["headBranch"] = "fix/other"
    gh, events = _gh_stub_recorded(tmp_path, [holder, behind, other],
                                   {210: 0, 211: 0, 213: 0}, open_issues=[], monkeypatch=monkeypatch)
    rc = czp.main(["--repo", "asimov-agent/llgenie", "--minutes", "30", "--cancel-stranded"])
    out = capsys.readouterr().out
    assert rc == 1, out
    ev = _events(events)
    cancels = sorted(int(e.split(":", 1)[1]) for e in ev if e.startswith("run_cancel"))
    assert cancels == [210, 213], ev                          # 211 is never on the cancel list
    assert not any("211" in e for e in ev), ev
    assert not any(e.startswith("issue_create") for e in ev), ev  # cancel-only files nothing
    assert "cancelled 2 stranded" in out, out


def test_cancel_refusal_retires_the_run_with_a_record_and_clears_the_gate(tmp_path, monkeypatch, capsys):
    """Zombie retirement (issue #2600): GitHub answers `run cancel` with 'already completed' while the
    run LIST row stays `queued` forever (measured on 43096752613/43098130674: REST queued, cancel
    refuses 'completed', delete 403). The refusal confirms conclusion: the run is RETIRED with a
    deduped retirement record (marker `zero-job-zombie-retired`), never filed stranded, never forced
    RED — and when every candidate retired, the gate exits 0. This is what makes 'the same run is
    never reported a second time' (#2588's criterion) mechanically true."""
    r = _run(7, "queued", 1600.0); r["headBranch"] = "feat/a"
    gh, events = _gh_stub_recorded(
        tmp_path, [r], {7: 0}, open_issues=[], monkeypatch=monkeypatch,
        cancel_errors={7: "run 7 cannot be cancelled. The run has already completed."})
    rc = czp.main(["--repo", "asimov-agent/llgenie", "--minutes", "30", "--file", "--cancel-stranded"])
    cap = capsys.readouterr()
    assert rc == 0, cap.out + cap.err          # confirmed-concluded + record on file → gate clears
    assert "DELIVERY FAILED" not in cap.out + cap.err, cap.out + cap.err
    assert "1 confirmed-concluded run(s) retired" in cap.out, cap.out
    ev = _events(events)
    assert any(e.startswith("run_cancel") for e in ev), ev          # truth-probe attempted
    creates = [e for e in ev if e.startswith("issue_create")]
    assert len(creates) == 1, ev                                    # exactly one retirement record
    assert not any(e.startswith("check_runs_post") for e in ev), ev  # a concluded run is not forced RED
    create = json.loads(creates[0].split(":", 1)[1])
    body = create[create.index("--body") + 1]
    assert "<!-- zero-job-zombie-retired: run 7 -->" in body, body[:400]
    assert "confirmed concluded per the cancel API" in create[create.index("--title") + 1], create


def test_a_retired_run_is_never_counted_again(tmp_path, monkeypatch, capsys):
    """Read-only scan, one week later: the phantom list row still says `queued`, but its retirement
    marker is on an issue (open OR closed). The scan names it zombie-retired, counts no finding,
    spends no cancel, files nothing, and exits 0 — the gate clears for good (issue #2600)."""
    r = _run(9, "queued", 1600.0); r["headBranch"] = "feat/b"
    gh, events = _gh_stub_recorded(
        tmp_path, [r], {9: 0},
        open_issues=[{"body": "retired earlier <!-- zero-job-zombie-retired: run 9 -->"}],
        monkeypatch=monkeypatch)
    rc = czp.main(["--repo", "asimov-agent/llgenie", "--minutes", "30"])
    out = capsys.readouterr().out
    assert rc == 0, out
    assert "zombie-retired 1 run(s)" in out, out
    assert "run 9" in out, out
    assert "ZERO jobs" not in out, out          # not counted as a finding
    ev = _events(events)
    assert not any(e.startswith(("run_cancel", "issue_create", "check_runs_post")) for e in ev), ev


def test_live_starvation_stays_red_alongside_a_retired_zombie(tmp_path, monkeypatch, capsys):
    """The retirement must not soften the alarm: a NEW stranded run in the same scan is cancelled,
    filed and forced RED as before (rc 1), while the marker-retired zombie is only named."""
    live = _run(7, "queued", 60.0); live["headBranch"] = "feat/a"
    zombie = _run(9, "queued", 1600.0); zombie["headBranch"] = "feat/b"
    gh, events = _gh_stub_recorded(
        tmp_path, [live, zombie], {7: 0, 9: 0},
        open_issues=[{"body": "retired <!-- zero-job-zombie-retired: run 9 -->"}],
        monkeypatch=monkeypatch)
    rc = czp.main(["--repo", "asimov-agent/llgenie", "--minutes", "30", "--file", "--cancel-stranded"])
    out = capsys.readouterr().out
    assert rc == 1, out
    assert "zombie-retired 1 run(s)" in out, out
    assert "cancelled 1 stranded" in out, out
    ev = _events(events)
    cancels = [e.split(":", 1)[1] for e in ev if e.startswith("run_cancel")]
    assert cancels == ["7"], ev                                       # the zombie is never re-cancelled
    assert sum(1 for e in ev if e.startswith("issue_create")) == 1, ev  # only the live run is filed
    assert sum(1 for e in ev if e.startswith("check_runs_post")) == 1, ev  # RED only for the live head


def test_a_retirement_record_that_fails_to_land_keeps_the_gate_loud(tmp_path, monkeypatch, capsys):
    """Delivery stays loud (#294): a confirmed-concluded run whose retirement issue fails is a
    DELIVERY FAILED exit 3 — the gate never greens on an unrecorded confirmation."""
    r = _run(7, "queued", 1600.0); r["headBranch"] = "feat/a"
    gh, events = _gh_stub_recorded(
        tmp_path, [r], {7: 0}, open_issues=[], monkeypatch=monkeypatch,
        cancel_errors={7: "run 7 cannot be cancelled. The run has already completed."},
        issue_create_error="issues: rate limit exceeded")
    rc = czp.main(["--repo", "asimov-agent/llgenie", "--minutes", "30", "--file", "--cancel-stranded"])
    cap = capsys.readouterr()
    assert rc == 3, cap.out + cap.err
    assert "DELIVERY FAILED" in cap.err, cap.err
    assert "retirement record for run 7 failed" in cap.err, cap.err
