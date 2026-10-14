"""The queued-run alarm: a stuck runner must be loud, not an eternal `pending` (issue #254).

`gh` is stubbed on PATH (the repo's allowance for an external CLI), so the decision logic runs
for real: which jobs count as stuck, what the report says, when the sweep goes red, and that the
comment is posted exactly once per run.
"""
from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ALARM = REPO / "scripts" / "queued_run_alarm.py"
sys.path.insert(0, str(REPO / "scripts"))
import queued_run_alarm as alarm  # noqa: E402

OWNER = "asimov-agent"


def gh_stub(tmp_path: Path, runs, jobs: dict, existing_comments: dict | None = None,
            fail=False, job_details: dict | None = None) -> Path:
    """A `gh` that answers run list / run view / issue comments and logs a POST."""
    bin_dir = tmp_path / "bin"; bin_dir.mkdir(exist_ok=True)
    scenario = tmp_path / "scenario.json"
    scenario.write_text(json.dumps({"runs": runs, "jobs": jobs,
                                    "comments": existing_comments or {},
                                    "details": job_details or {}}))
    log = tmp_path / "gh-calls"; log.write_text("")
    gh = bin_dir / "gh"
    gh.write_text(f"""#!/usr/bin/env python3
import json, pathlib, sys
sc = json.loads(pathlib.Path("{scenario}").read_text())
a = sys.argv[1:]
with open("{log}", "a") as fh:
    print(" ".join(a), file=fh)
if {"fail" if fail else "False"}:
    sys.exit(1)
if a[:2] == ["run", "list"]:
    # answer per requested status: the fixtures describe all runs
    print(json.dumps(sc["runs"]))
elif a[:2] == ["run", "view"]:
    print(json.dumps({{"jobs": sc["jobs"].get(a[2], [])}}))
elif a[:1] == ["api"] and "-X" not in a and "/actions/jobs/" in a[1]:
    print(json.dumps(sc["details"].get(a[1].split("/")[-1], {{}})))
elif a[:1] == ["api"] and "-X" not in a:
    rid = a[1].rstrip("/comments").split("/")[-1]
    print(json.dumps(sc["comments"].get(rid, [])))
elif a[:1] == ["api"]:
    pass
else:
    sys.exit(f"unexpected gh call: {{a}}")
""")
    gh.chmod(gh.stat().st_mode | stat.S_IEXEC)
    return log


def run_alarm(tmp_path: Path, args: list[str]):
    env = dict(os.environ)
    env["PATH"] = f"{tmp_path / 'bin'}:{env['PATH']}"
    return subprocess.run([sys.executable, str(ALARM), *args], cwd=str(tmp_path),
                          env=env, capture_output=True, text=True, timeout=60)


def job(name, status="queued", started="2026-10-14T04:22:35Z", labels=("macos-15-intel",)):
    return {"name": name, "status": status, "startedAt": started, "labels": list(labels)}


RUN = [{"databaseId": 111, "workflowName": "CI", "headBranch": "main", "url": "u"}]


def test_a_long_queued_job_is_reported_and_goes_red(tmp_path):
    gh_stub(tmp_path, RUN, {"111": [job("macos / unit")]})
    r = run_alarm(tmp_path, ["--repo", f"{OWNER}/llgenie", "--minutes", "30"])
    assert r.returncode == 1, "a stuck job must make the sweep red, not silent"
    assert "macos / unit" in r.stdout and "macos-15-intel" in r.stdout
    assert "3" in r.stdout or "queued longer than 30 minutes" in r.stdout
    assert "no machine matches those labels" in r.stdout
    assert "#254" in r.stdout, "the report points at the issue that tracks the cause"


def test_a_recently_queued_job_is_not_reported(tmp_path):
    """A job that has only just been queued is normal; only a stuck one is news."""
    gh_stub(tmp_path, RUN, {"111": [job("macos / unit", started="2999-01-01T00:00:00Z")]})
    r = run_alarm(tmp_path, ["--repo", f"{OWNER}/llgenie", "--minutes", "30"])
    assert r.returncode == 0
    assert "no job has been queued longer" in r.stdout


def test_running_and_finished_jobs_are_ignored(tmp_path):
    gh_stub(tmp_path, RUN, {"111": [job("linux / unit", status="in_progress"),
                                    job("macos / lint", status="completed")]})
    r = run_alarm(tmp_path, ["--repo", f"{OWNER}/llgenie"])
    assert r.returncode == 0 and "no job has been queued" in r.stdout


def test_the_threshold_is_a_parameter(tmp_path):
    gh_stub(tmp_path, RUN, {"111": [job("macos / unit", started="2026-10-14T04:22:35Z")]})
    assert run_alarm(tmp_path, ["--repo", f"{OWNER}/llgenie", "--minutes", "100000"]).returncode == 0
    assert run_alarm(tmp_path, ["--repo", f"{OWNER}/llgenie", "--minutes", "0.1"]).returncode == 1


def test_comment_is_posted_once_per_run(tmp_path):
    log = gh_stub(tmp_path, RUN, {"111": [job("macos / unit")]})
    run_alarm(tmp_path, ["--repo", f"{OWNER}/llgenie", "--comment"])
    posts = [l for l in log.read_text().splitlines() if l.startswith("api -X POST")]
    assert len(posts) == 1 and "issues/111/comments" in posts[0]


def test_a_second_sweep_does_not_comment_again(tmp_path):
    """The tool's own marker keeps a twice-an-hour sweep from spamming the run."""
    gh_stub(tmp_path, RUN, {"111": [job("macos / unit")]},
            existing_comments={"111": [{"body": "old\n\n_<!-- queued-run-alarm -->_"}]})
    log = gh_stub(tmp_path, RUN, {"111": [job("macos / unit")]},
                  existing_comments={"111": [{"body": "old\n\n_<!-- queued-run-alarm -->_"}]})
    r = run_alarm(tmp_path, ["--repo", f"{OWNER}/llgenie", "--comment"])
    assert r.returncode == 1
    assert not [l for l in log.read_text().splitlines() if l.startswith("api -X POST")]


def test_a_github_failure_is_a_loud_exit_2(tmp_path):
    gh_stub(tmp_path, RUN, {}, fail=True)
    r = run_alarm(tmp_path, ["--repo", f"{OWNER}/llgenie"])
    assert r.returncode == 2 and "failed" in r.stderr


def test_the_report_names_every_label_it_saw(tmp_path):
    gh_stub(tmp_path, RUN, {"111": [job("macos / unit"), job("macos / lint", labels=("macos-14",))]})
    r = run_alarm(tmp_path, ["--repo", f"{OWNER}/llgenie"])
    assert "macos-14" in r.stdout and "macos-15-intel" in r.stdout
    assert "2 job(s) queued" in r.stdout


def test_it_asks_for_queued_runs_too_not_only_in_progress(tmp_path):
    """A run whose jobs are all queued has status `queued` — an in_progress-only query misses
    exactly the stuck state this alarm exists for (found by running it live)."""
    log = gh_stub(tmp_path, RUN, {"111": [job("macos / unit")]})
    run_alarm(tmp_path, ["--repo", f"{OWNER}/llgenie"])
    lists = [l for l in log.read_text().splitlines() if l.startswith("run list")]
    statuses = [l.split("--status ")[1].split()[0] for l in lists]
    assert "queued" in statuses, f"the queued run status must be queried: {statuses}"
    assert "in_progress" in statuses, statuses


def test_a_run_found_twice_is_reported_once(tmp_path):
    """Both status queries return the same run here; it must not be reported twice."""
    gh_stub(tmp_path, RUN, {"111": [job("macos / unit")]})
    r = run_alarm(tmp_path, ["--repo", f"{OWNER}/llgenie"])
    assert r.returncode == 1
    assert r.stdout.count("macos / unit") == 1, r.stdout
    assert "1 job(s) queued" in r.stdout, "the run is counted once, not once per query"


def test_the_label_is_filled_from_the_job_api_when_the_list_omits_it(tmp_path):
    """`gh run view --json jobs` can leave labels empty; the job API has the label, and the
    label is what tells a maintainer WHICH runner is missing (issue #254)."""
    gh_stub(tmp_path, RUN, {"111": [job("macos / unit", labels=())]},
            job_details={"501": {"labels": ["macos-15-intel"], "runner_name": ""}})
    # the fixture job needs an id for the detail lookup
    (tmp_path / "scenario.json").write_text((tmp_path / "scenario.json").read_text().replace(
        '"labels": []', '"labels": [], "databaseId": 501'))
    r = run_alarm(tmp_path, ["--repo", f"{OWNER}/llgenie"])
    assert r.returncode == 1
    assert "macos-15-intel" in r.stdout, r.stdout


def test_a_failed_detail_lookup_still_reports_the_job(tmp_path):
    """The alarm must never lose a stuck job because a detail call failed."""
    gh_stub(tmp_path, RUN, {"111": [job("macos / unit", labels=())]}, job_details={})
    (tmp_path / "scenario.json").write_text((tmp_path / "scenario.json").read_text().replace(
        '"labels": []', '"labels": [], "databaseId": 501'))
    r = run_alarm(tmp_path, ["--repo", f"{OWNER}/llgenie"])
    assert r.returncode == 1 and "macos / unit" in r.stdout


def test_the_age_is_computed_from_the_job_start(tmp_path):
    import datetime as dt
    now = dt.datetime(2026, 10, 14, 6, 0, 0, tzinfo=dt.timezone.utc)
    assert alarm._age_minutes("2026-10-14T04:22:35Z", now) == 97.4
    assert alarm._age_minutes(None, now) is None
    assert alarm._age_minutes("not a date", now) is None
