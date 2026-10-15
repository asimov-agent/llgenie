"""The queued-run alarm: a stuck runner must be loud, not an eternal `pending` (issue #254).

`gh` is stubbed on PATH (the repo's allowance for an external CLI), so the decision logic runs
for real: which jobs count as stuck, what the report says, when the sweep goes red, and WHERE the
report lands.

A workflow run id is not an issue number — the first version posted to `/issues/{run_id}/comments`
and every POST 404'd while the job stayed green (#294). So the delivery is asserted by TARGET: the
PR the run's head branch belongs to, else one deduped issue per stuck runner label, and a delivery
that fails makes the run fail (exit 3) instead of passing quietly.

Two CLI facts measured live (gh 2.102.0) are pinned below, because a fake `gh` that answers
whatever the code asks is exactly how the run-id bug shipped:

  * `gh run view --json` has NO `pullRequests` field ("Unknown JSON field: pullRequests");
  * the REST run object's `pull_requests` array is EMPTY for a fork-PR run (#277, #170), so the PR
    is resolved from the run's head branch with `gh pr list --head <branch>`.
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
            fail=False, job_details: dict | None = None, run_meta: dict | None = None,
            pr_list: dict | None = None, open_issues: list | None = None,
            fail_post=False, fail_run_meta=False) -> Path:
    """A `gh` answering run list / run view / the REST run object / pr list / comments / issue
    list, logging every mutating call so the TARGET can be asserted."""
    bin_dir = tmp_path / "bin"; bin_dir.mkdir(exist_ok=True)
    scenario = tmp_path / "scenario.json"
    scenario.write_text(json.dumps({"runs": runs, "jobs": jobs,
                                    "comments": existing_comments or {},
                                    "details": job_details or {},
                                    "run_meta": run_meta or {},
                                    "pr_list": pr_list or {},
                                    "issues": open_issues or []}))
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
POSTING = (a[:1] == ["api"] and "-X" in a) or a[:2] == ["issue", "create"]
if POSTING:
    if {"fail_post" if fail_post else "False"}:
        print("HTTP 404: Not Found", file=sys.stderr)
        sys.exit(1)
    sys.exit(0)
if "/actions/runs/" in " ".join(a):
    rid = a[1].split("/")[-1]
    if {"fail_run_meta" if fail_run_meta else "False"}:
        print("HTTP 500: boom", file=sys.stderr)
        sys.exit(1)
    print(json.dumps(sc["run_meta"].get(rid, {{}})))
elif a[:2] == ["run", "list"]:
    # answer per requested status: the fixtures describe all runs
    print(json.dumps(sc["runs"]))
elif a[:2] == ["run", "view"]:
    print(json.dumps({{"jobs": sc["jobs"].get(a[2], [])}}))
elif a[:2] == ["pr", "list"]:
    print(json.dumps(sc["pr_list"].get(a[a.index("--head") + 1], [])))
elif a[:2] == ["issue", "list"]:
    print(json.dumps(sc["issues"]))
elif a[:1] == ["api"] and "/actions/jobs/" in a[1]:
    print(json.dumps(sc["details"].get(a[1].split("/")[-1], {{}})))
elif a[:1] == ["api"]:
    rid = a[1].rstrip("/comments").split("/")[-1]
    print(json.dumps(sc["comments"].get(rid, [])))
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


RUN = [{"databaseId": 111, "workflowName": "CI", "headBranch": "fix/thing", "url": "u"}]
#: A pull_request run (the normal case): run 111 reports on PR 42, head branch `fix/thing`.
RUN_META = {"111": {"event": "pull_request", "head_branch": "fix/thing"}}
PR_LIST = {"fix/thing": [{"number": 42, "state": "OPEN"}]}
#: A schedule/push run: no pull request anywhere.
RUN_META_PUSH = {"111": {"event": "schedule", "head_branch": "main"}}
REPO_SLUG = f"{OWNER}/llgenie"


def test_a_long_queued_job_is_reported_and_goes_red(tmp_path):
    gh_stub(tmp_path, RUN, {"111": [job("macos / unit")]})
    r = run_alarm(tmp_path, ["--repo", REPO_SLUG, "--minutes", "30"])
    assert r.returncode == 1, "a stuck job must make the sweep red, not silent"
    assert "macos / unit" in r.stdout and "macos-15-intel" in r.stdout
    assert "3" in r.stdout or "queued longer than 30 minutes" in r.stdout
    assert "no machine matches those labels" in r.stdout
    assert "#254" in r.stdout, "the report points at the issue that tracks the cause"


def test_a_recently_queued_job_is_not_reported(tmp_path):
    """A job that has only just been queued is normal; only a stuck one is news."""
    gh_stub(tmp_path, RUN, {"111": [job("macos / unit", started="2999-01-01T00:00:00Z")]})
    r = run_alarm(tmp_path, ["--repo", REPO_SLUG, "--minutes", "30"])
    assert r.returncode == 0
    assert "no job has been queued longer" in r.stdout


def test_running_and_finished_jobs_are_ignored(tmp_path):
    gh_stub(tmp_path, RUN, {"111": [job("linux / unit", status="in_progress"),
                                    job("macos / lint", status="completed")]})
    r = run_alarm(tmp_path, ["--repo", REPO_SLUG])
    assert r.returncode == 0 and "no job has been queued" in r.stdout


def test_the_threshold_is_a_parameter(tmp_path):
    gh_stub(tmp_path, RUN, {"111": [job("macos / unit", started="2026-10-14T04:22:35Z")]})
    assert run_alarm(tmp_path, ["--repo", REPO_SLUG, "--minutes", "100000"]).returncode == 0
    assert run_alarm(tmp_path, ["--repo", REPO_SLUG, "--minutes", "0.1"]).returncode == 1


def test_the_report_goes_on_the_run_s_pull_request(tmp_path):
    """#294: the report is posted where a human reads it — the PR — and NEVER to `/issues/<run id>`."""
    log = gh_stub(tmp_path, RUN, {"111": [job("macos / unit")]},
                  run_meta=RUN_META, pr_list=PR_LIST)
    r = run_alarm(tmp_path, ["--repo", REPO_SLUG, "--comment"])
    assert r.returncode == 1
    calls = log.read_text().splitlines()
    posts = [c for c in calls if c.startswith("api -X POST")]
    assert len(posts) == 1, f"exactly one comment, got {posts}"
    assert "/issues/42/comments" in posts[0], posts[0]
    assert "/issues/111/comments" not in " ".join(calls), (
        "a workflow RUN id is not an issue number: that POST 404s and the alarm writes nowhere"
    )
    assert "delivered" in r.stdout


def test_the_pr_is_found_from_the_head_branch(tmp_path):
    """Measured live: a FORK-PR run's REST `pull_requests` is empty (#277, #170) and
    `gh run view --json` rejects a `pullRequests` field outright — so the head branch is the link."""
    log = gh_stub(tmp_path, RUN, {"111": [job("macos / unit")]},
                  run_meta=RUN_META, pr_list=PR_LIST)
    run_alarm(tmp_path, ["--repo", REPO_SLUG, "--comment"])
    calls = log.read_text().splitlines()
    assert "api /repos/asimov-agent/llgenie/actions/runs/111" in calls, calls
    assert any(c.startswith("pr list") and "--head fix/thing" in c for c in calls), calls
    assert not [c for c in calls if c.startswith("run view") and "pullRequests" in c], calls


def test_a_second_sweep_does_not_comment_again(tmp_path):
    """The tool's own per-run marker keeps a twice-an-hour sweep from spamming the PR."""
    marker = "old\n\n_" + alarm.run_marker(111) + "_"
    log = gh_stub(tmp_path, RUN, {"111": [job("macos / unit")]}, run_meta=RUN_META, pr_list=PR_LIST,
                  existing_comments={"42": [{"body": marker}]})
    r = run_alarm(tmp_path, ["--repo", REPO_SLUG, "--comment"])
    assert r.returncode == 1
    assert not [c for c in log.read_text().splitlines() if c.startswith("api -X POST")]


def test_a_run_with_no_pr_files_one_deduped_issue_per_label(tmp_path):
    """A schedule/push run has no PR: the missing runner is a property of the LABEL, so the
    fallback is ONE issue per label, and a second sweep files nothing."""
    log = gh_stub(tmp_path, RUN, {"111": [job("macos / unit")]}, run_meta=RUN_META_PUSH)
    r = run_alarm(tmp_path, ["--repo", REPO_SLUG, "--comment"])
    assert r.returncode == 1
    creates = [c for c in log.read_text().splitlines() if c.startswith("issue create")]
    assert len(creates) == 1, creates
    assert "macos-15-intel" in creates[0], creates[0]
    assert not [c for c in log.read_text().splitlines() if c.startswith("api -X POST")]

    # Given that issue is already open (the marker in its body), a second sweep files nothing
    log2 = gh_stub(tmp_path, RUN, {"111": [job("macos / unit")]}, run_meta=RUN_META_PUSH,
                   open_issues=[{"number": 7,
                                 "body": "x\n" + alarm.label_marker("macos-15-intel")}])
    r2 = run_alarm(tmp_path, ["--repo", REPO_SLUG, "--comment"])
    assert r2.returncode == 1
    assert not [c for c in log2.read_text().splitlines() if c.startswith("issue create")]


def test_a_failed_delivery_is_a_loud_exit_3(tmp_path):
    """The bug in #294 was a silent one: a report that never lands must fail the run."""
    gh_stub(tmp_path, RUN, {"111": [job("macos / unit")]}, run_meta=RUN_META, pr_list=PR_LIST,
            fail_post=True)
    r = run_alarm(tmp_path, ["--repo", REPO_SLUG, "--comment"])
    assert r.returncode == 3, r.stdout + r.stderr
    assert "DELIVERY FAILED" in r.stderr


def test_a_failed_pr_lookup_is_loud_and_still_reports(tmp_path):
    """A run whose PR cannot be resolved is an error (exit 3) — and the report still lands on the
    fallback issue, so the stuck job is not lost."""
    log = gh_stub(tmp_path, RUN, {"111": [job("macos / unit")]}, run_meta=RUN_META,
                  pr_list=PR_LIST, fail_run_meta=True)
    r = run_alarm(tmp_path, ["--repo", REPO_SLUG, "--comment"])
    assert r.returncode == 3, r.stdout + r.stderr
    assert "could not read the pull requests of run 111" in r.stderr
    assert "issue create" in log.read_text(), "the report still lands somewhere a human reads"


def test_dry_reports_what_it_would_post_and_posts_nothing(tmp_path):
    log = gh_stub(tmp_path, RUN, {"111": [job("macos / unit")]}, run_meta=RUN_META, pr_list=PR_LIST)
    r = run_alarm(tmp_path, ["--repo", REPO_SLUG, "--dry"])
    assert r.returncode == 1, "a stuck job is still red in a dry run"
    assert "would be delivered" in r.stdout
    mutating = [c for c in log.read_text().splitlines()
                if c.startswith("api -X POST") or c.startswith("issue create")]
    assert not mutating, mutating


def test_a_github_failure_is_a_loud_exit_2(tmp_path):
    gh_stub(tmp_path, RUN, {}, fail=True)
    r = run_alarm(tmp_path, ["--repo", REPO_SLUG])
    assert r.returncode == 2 and "failed" in r.stderr


def test_the_report_names_every_label_it_saw(tmp_path):
    gh_stub(tmp_path, RUN, {"111": [job("macos / unit"), job("macos / lint", labels=("macos-14",))]})
    r = run_alarm(tmp_path, ["--repo", REPO_SLUG])
    assert "macos-14" in r.stdout and "macos-15-intel" in r.stdout
    assert "2 job(s) queued" in r.stdout


def test_it_asks_for_queued_runs_too_not_only_in_progress(tmp_path):
    """A run whose jobs are all queued has status `queued` — an in_progress-only query misses
    exactly the stuck state this alarm exists for (found by running it live)."""
    log = gh_stub(tmp_path, RUN, {"111": [job("macos / unit")]})
    run_alarm(tmp_path, ["--repo", REPO_SLUG])
    lists = [l for l in log.read_text().splitlines() if l.startswith("run list")]
    statuses = [l.split("--status ")[1].split()[0] for l in lists]
    assert "queued" in statuses, f"the queued run status must be queried: {statuses}"
    assert "in_progress" in statuses, statuses


def test_a_run_found_twice_is_reported_once(tmp_path):
    """Both status queries return the same run here; it must not be reported twice."""
    gh_stub(tmp_path, RUN, {"111": [job("macos / unit")]})
    r = run_alarm(tmp_path, ["--repo", REPO_SLUG])
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
    r = run_alarm(tmp_path, ["--repo", REPO_SLUG])
    assert r.returncode == 1
    assert "macos-15-intel" in r.stdout, r.stdout


def test_a_failed_detail_lookup_still_reports_the_job(tmp_path):
    """The alarm must never lose a stuck job because a detail call failed."""
    gh_stub(tmp_path, RUN, {"111": [job("macos / unit", labels=())]}, job_details={})
    (tmp_path / "scenario.json").write_text((tmp_path / "scenario.json").read_text().replace(
        '"labels": []', '"labels": [], "databaseId": 501'))
    r = run_alarm(tmp_path, ["--repo", REPO_SLUG])
    assert r.returncode == 1 and "macos / unit" in r.stdout


def test_the_markers_name_the_run_and_the_label():
    """Two subjects, two markers: a run's news is per run, a missing runner is per label."""
    assert alarm.run_marker(111) == "<!-- queued-run-alarm: run 111 -->"
    assert alarm.label_marker("macos-15-intel") == "<!-- queued-run-alarm: label macos-15-intel -->"


def test_the_age_is_computed_from_the_job_start():
    import datetime as dt
    now = dt.datetime(2026, 10, 14, 6, 0, 0, tzinfo=dt.timezone.utc)
    assert alarm._age_minutes("2026-10-14T04:22:35Z", now) == 97.4
    assert alarm._age_minutes(None, now) is None
    assert alarm._age_minutes("not a date", now) is None
