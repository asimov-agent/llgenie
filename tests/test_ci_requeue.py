"""The cancellation healer (issue #843): a killed run is re-queued, a superseded one is left alone.

A `cancelled` run is not a verdict — `gh pr checks` shows it as `fail`, `auto-merge` needs a green
run, and the reactor fires only on `conclusion: failure` — so a bulk cancel that frees the runner
queue silently costs every killed PR its answer. `scripts/ci_requeue.py` is the other half: it
re-runs a cancelled run ONLY when its head sha has no other run, and never touches a run a newer
commit already superseded.

Driven through a fake `gh` that records argv, so the assertions are about the exact requests.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import ci_requeue as rq  # noqa: E402


def _iso(hours_ago: float, now: dt.datetime) -> str:
    return (now - dt.timedelta(hours=hours_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _fake_gh(tmp_path: Path, runs: list[dict], sha_runs: dict[str, int]):
    """A `gh` that serves the two list endpoints and records every `run rerun` it is given."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "runs.json").write_text(json.dumps(runs))
    (tmp_path / "sha_runs.json").write_text(json.dumps(sha_runs))
    log = tmp_path / "gh.log"
    gh = tmp_path / "gh"
    gh.write_text(f'''#!{sys.executable}
import json, sys, pathlib
here = pathlib.Path(__file__).parent
args = sys.argv[1:]
with open({str(log)!r}, "a") as fh:
    fh.write(json.dumps(args) + "\\n")
if args[:2] == ["run", "rerun"]:
    print("")
    sys.exit(0)
url = args[1] if len(args) > 1 else ""
if "head_sha=" in url:
    sha = url.split("head_sha=")[1].split("&")[0]
    n = json.loads((here / "sha_runs.json").read_text()).get(sha, 1)
    print(json.dumps({{"workflow_runs": [{{"id": i}} for i in range(n)]}}))
elif "actions/runs" in url:
    page = int(url.rsplit("page=", 1)[1]) if "page=" in url else 1
    runs = json.loads((here / "runs.json").read_text()) if page == 1 else []
    print(json.dumps({{"workflow_runs": runs}}))
else:
    print("{{}}")
''')
    gh.chmod(0o755)
    return gh, log


def _calls(log: Path) -> list[list[str]]:
    if not log.exists():
        return []
    return [json.loads(line) for line in log.read_text().splitlines() if line.strip()]


def _run_record(num: int, sha: str, concluded: str, hours_ago: float, now: dt.datetime,
                branch: str = "feat/x", workflow: int = 1, event: str = "push") -> dict:
    return {"id": num, "name": "CI" if workflow == 1 else "scope", "workflow_id": workflow,
            "head_sha": sha, "head_branch": branch, "conclusion": concluded, "event": event,
            "created_at": _iso(hours_ago, now), "status": "completed"}


def test_a_cancelled_run_with_no_successor_is_re_queued(tmp_path, monkeypatch, capsys):
    """The measured case: the only run on that sha, cancelled mid-flight (#843)."""

    # Given a run cancelled 30 minutes ago whose head sha has exactly one run
    now = dt.datetime.now(dt.timezone.utc)   # the CLI reads the real clock; fixtures hang off it
    gh, log = _fake_gh(tmp_path, [_run_record(111, "a" * 40, "cancelled", 0.5, now)], {"a" * 40: 1})
    monkeypatch.setenv("CI_REQUEUE_GH", str(gh))

    # When  the healer runs over a 2h window
    assert rq.main(["run", "--repo", "asimov-agent/llgenie", "--window", "2h"]) == 0

    # Then  it re-runs exactly that run, and says so
    reruns = [c for c in _calls(log) if c[:2] == ["run", "rerun"]]
    assert reruns == [["run", "rerun", "111", "--repo", "asimov-agent/llgenie", "--failed"]], reruns
    assert "re-ran 111" in capsys.readouterr().out


def test_a_superseded_cancelled_run_is_left_alone(tmp_path, monkeypatch, capsys):
    """`cancel-in-progress` cancels the PREVIOUS run: a later run of the same workflow owns the verdict."""

    # Given a cancelled run AND a later run of the same workflow on the same branch
    now = dt.datetime.now(dt.timezone.utc)   # the CLI reads the real clock; fixtures hang off it
    runs = [_run_record(222, "b" * 40, "cancelled", 0.5, now, branch="feat/x"),
            _run_record(223, "b" * 40, "success", 0.2, now, branch="feat/x")]
    gh, log = _fake_gh(tmp_path, runs, {"b" * 40: 2})
    monkeypatch.setenv("CI_REQUEUE_GH", str(gh))

    # When  the healer runs
    assert rq.main(["run"]) == 0

    # Then  nothing is re-run, and the pass-over is stated with its reason
    assert [c for c in _calls(log) if c[:2] == ["run", "rerun"]] == []
    assert "superseded" in capsys.readouterr().out


def test_a_cancelled_workflow_run_triggered_run_is_skipped_but_not_fatal(tmp_path, monkeypatch, capsys):
    """#1451: a cancelled `workflow_run`-triggered run (auto-merge, ci-verdict, reactor completing)
    cannot be retried by GitHub — it must be passed over with the reason, and every retryable
    cancellation in the window must still be re-run. The negative control: the bug returns if the
    auto-merge cancellation aborts the heal before the retryable one is re-run."""
    # Given a cancelled `workflow_run` reaction (un-retryable) AND a retryable cancelled run
    now = dt.datetime.now(dt.timezone.utc)   # the CLI reads the real clock; fixtures hang off it
    runs = [_run_record(600, "6" * 40, "cancelled", 0.5, now, branch="main", workflow=1,
                        event="workflow_run"),
            _run_record(601, "6" * 40, "cancelled", 0.5, now, branch="feat/x", workflow=1)]
    gh, log = _fake_gh(tmp_path, runs, {"6" * 40: 2})
    monkeypatch.setenv("CI_REQUEUE_GH", str(gh))

    # When  the healer runs over the window
    assert rq.main(["run", "--repo", "asimov-agent/llgenie", "--window", "2h"]) == 0
    out = capsys.readouterr().out

    # Then  the retryable run is re-run, and the un-retryable one is named with why, not aborted
    reruns = [c for c in _calls(log) if c[:2] == ["run", "rerun"]]
    assert reruns == [["run", "rerun", "601", "--repo", "asimov-agent/llgenie", "--failed"]], reruns
    assert "re-ran 601" in out
    assert "keep 600" in out and "workflow_run-triggered" in out, out
    assert "workflow_run-triggered" not in reruns[0]


def test_plan_dry_names_a_cancelled_workflow_run_triggered_run(tmp_path, monkeypatch, capsys):
    """#1451 AC2: `plan` (and `run --dry`) must NAME the un-retryable run and why — never a silent
    list nothing happened, because a skip without a reason looks like a healed nothing."""
    # Given the same window with a cancelled workflow_run reaction and a retryable run
    now = dt.datetime.now(dt.timezone.utc)
    runs = [_run_record(602, "7" * 40, "cancelled", 0.5, now, branch="main", event="workflow_run"),
            _run_record(603, "7" * 40, "cancelled", 0.5, now, branch="feat/y")]
    gh, _log = _fake_gh(tmp_path, runs, {"7" * 40: 2})
    monkeypatch.setenv("CI_REQUEUE_GH", str(gh))

    # When  the planner runs
    requeue, skipped = rq.plan("asimov-agent/llgenie", rq.parse_window("2h"), now=now)

    # Then  the retryable one is planned and the workflow_run one is recorded with its reason
    assert [r["id"] for r in requeue] == [603], (requeue, skipped)
    assert [r["id"] for r in skipped] == [602], (requeue, skipped)
    assert "workflow_run-triggered" in skipped[0]["why"], skipped


def test_another_workflow_on_the_same_commit_does_not_supersede(tmp_path, monkeypatch):
    """A PR that also runs `scope`/`docs` on the same sha must still have its cancelled CI healed."""

    # Given a cancelled CI run and a SUCCESSFUL run of a DIFFERENT workflow on the same branch
    now = dt.datetime.now(dt.timezone.utc)   # the CLI reads the real clock; fixtures hang off it
    runs = [_run_record(555, "1" * 40, "cancelled", 0.5, now, branch="feat/x", workflow=1),
            _run_record(556, "1" * 40, "success", 0.2, now, branch="feat/x", workflow=2)]
    gh, _log = _fake_gh(tmp_path, runs, {"1" * 40: 2})
    monkeypatch.setenv("CI_REQUEUE_GH", str(gh))

    # When  the healer plans
    requeue, skipped = rq.plan("asimov-agent/llgenie", rq.parse_window("2h"), now=now)

    # Then  the cancelled CI run is still a candidate — another workflow is not this one's verdict
    assert [r["id"] for r in requeue] == [555], (requeue, skipped)


def test_dry_re_runs_nothing_but_prints_the_plan(tmp_path, monkeypatch, capsys):
    """`DRY=1` is how a reader checks the healer without spending runners."""

    # Given a re-runnable cancellation
    now = dt.datetime.now(dt.timezone.utc)   # the CLI reads the real clock; fixtures hang off it
    gh, log = _fake_gh(tmp_path, [_run_record(333, "c" * 40, "cancelled", 0.5, now)], {"c" * 40: 1})
    monkeypatch.setenv("CI_REQUEUE_GH", str(gh))

    # When  it runs with --dry
    assert rq.main(["run", "--dry"]) == 0
    out = capsys.readouterr().out

    # Then  nothing was dispatched, and the plan names the run
    assert [c for c in _calls(log) if c[:2] == ["run", "rerun"]] == []
    assert "DRY would re-run 333" in out and "would re-run 1 cancelled run(s)" in out


def test_a_kill_older_than_the_window_is_not_healed(tmp_path, monkeypatch):
    """A day-old cancellation has been superseded by the author or the next commit in practice."""

    # Given a cancellation 5 hours old and a 2h window
    now = dt.datetime.now(dt.timezone.utc)   # the CLI reads the real clock; fixtures hang off it
    gh, log = _fake_gh(tmp_path, [_run_record(444, "d" * 40, "cancelled", 5, now)], {"d" * 40: 1})
    monkeypatch.setenv("CI_REQUEUE_GH", str(gh))

    # When  the healer plans over 2h
    requeue, _skipped = rq.plan("asimov-agent/llgenie", rq.parse_window("2h"), now=now)

    # Then  the old run is outside the window
    assert requeue == []


def test_only_cancelled_runs_are_candidates(tmp_path, monkeypatch):
    """A failed run is the reactor's business; a green one is nobody's. Only cancellations are healed."""

    # Given one run of each conclusion, all on their own sha
    now = dt.datetime.now(dt.timezone.utc)   # the CLI reads the real clock; fixtures hang off it
    runs = [_run_record(1, "e" * 40, "cancelled", 0.2, now, branch="feat/a"),
            _run_record(2, "f" * 40, "failure", 0.2, now, branch="feat/b"),
            _run_record(3, "0" * 40, "success", 0.2, now, branch="feat/c")]
    gh, _log = _fake_gh(tmp_path, runs, {"e" * 40: 1, "f" * 40: 1, "0" * 40: 1})
    monkeypatch.setenv("CI_REQUEUE_GH", str(gh))

    # When  the healer plans
    requeue, _skipped = rq.plan("asimov-agent/llgenie", rq.parse_window("2h"), now=now)

    # Then  only the cancelled one is a candidate
    assert [r["id"] for r in requeue] == [1]


def test_the_window_parser_refuses_garbage():
    """A `--window` nobody can read must fail loudly, not silently heal nothing."""

    # Given a malformed window
    # When  it is parsed
    try:
        rq.parse_window("2 hours")
    except SystemExit as exc:
        # Then  the failure names the shape it wants
        assert "use e.g. 90m, 2h, 1d" in str(exc)
    else:                                    # pragma: no cover - the guard this test exists for
        raise AssertionError("a malformed window was accepted")
    assert rq.parse_window("90m") == dt.timedelta(minutes=90)
    assert rq.parse_window("1d") == dt.timedelta(days=1)


def test_the_scheduled_healer_is_wired_to_the_manual_target():
    """A cron that runs something other than the measured target is a schedule that heals nothing."""

    # Given the scheduled workflow this repository ships for the healer
    import pathlib
    import re

    import yaml

    path = pathlib.Path(__file__).resolve().parent.parent / ".github/workflows/ci-requeue.yml"
    wf = yaml.safe_load(path.read_text())
    on = wf.get("on") or wf.get(True)

    # Then  it fires every 30 minutes on minutes no other bot owns …
    crons = [str(slot.get("cron")) for slot in on["schedule"]]
    assert crons == ["15,45 * * * *"], crons

    # … it can be dispatched by hand …
    assert "workflow_dispatch" in on

    # … its round cannot be cancelled by the next round (that is the bug it heals) …
    assert wf["concurrency"] == {"group": "ci-requeue", "cancel-in-progress": False}

    # … it holds exactly the permissions `gh run rerun` needs, and no more …
    assert wf["permissions"] == {"contents": "read", "actions": "write", "pull-requests": "read"}

    steps = wf["jobs"]["requeue"]["steps"]

    # … it runs THE measured target, not a copy of its logic …
    assert any("make ci-requeue-cancelled" in (step.get("run") or "") for step in steps), steps

    # … and every action it uses is pinned to a full commit sha.
    for step in steps:
        if "uses" in step:
            assert re.fullmatch(r"[^@\s]+@[0-9a-f]{40}", step["uses"]), step["uses"]


# ---------------------------------------------------------------------------------------------------
# issue #846 / incident #767: a cancelled run that had been RUNNING a long time is a STALL, and that
# shape is invisible to both `gh pr checks` (it renders cancelled as fail) and a queue alarm (it only
# sees rows that never got a runner).
def _run(conclusion, started, updated, database_id=1):
    return {"database_id": database_id, "conclusion": conclusion, "created_at": started,
            "run_started_at": started, "updated_at": updated}


def test_a_long_cancelled_run_is_reported_as_a_stall():
    """The #767 shape: 30 minutes in flight, then killed with the matrix otherwise green."""

    # Given a run cancelled after 105 minutes and one cancelled after 2
    runs = [_run("cancelled", "2026-10-28T16:00:00Z", "2026-10-28T17:45:00Z", 1),
            _run("cancelled", "2026-10-28T16:00:00Z", "2026-10-28T16:02:00Z", 2)]

    # Then  only the long one is a stall, and its minutes are reported
    out = rq.stalls(runs, minimum_minutes=30)
    assert [r["database_id"] for r in out] == [1], out
    assert out[0]["minutes"] == 105.0, out


def test_a_successful_or_failed_run_is_never_a_stall():
    """A stall is about a run that was WORKING when it was killed."""

    runs = [_run("success", "2026-10-28T16:00:00Z", "2026-10-28T17:00:00Z", 1),
            _run("failure", "2026-10-28T16:00:00Z", "2026-10-28T17:00:00Z", 2)]

    assert rq.stalls(runs, minimum_minutes=30) == []


def test_stalls_are_ordered_by_how_long_they_ran():
    """The longest is the one that most likely hung, so it is the one to read first."""

    runs = [_run("cancelled", "2026-10-28T16:00:00Z", "2026-10-28T16:40:00Z", 1),
            _run("cancelled", "2026-10-28T16:00:00Z", "2026-10-28T17:45:00Z", 2)]

    assert [r["database_id"] for r in rq.stalls(runs, minimum_minutes=30)] == [2, 1]
