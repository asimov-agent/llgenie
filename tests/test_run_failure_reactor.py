"""The run-failure reactor: the route decision, the dedupe, and the claim protocol (issue #286).

The reactor decides through `gh`, which is stubbed on PATH here (the repo's allowance for an
external CLI), so the *decision logic* runs for real against controlled API answers: a red main run
with no PR becomes one deduped issue, the same head sha again files nothing, a red same-repo PR
dispatches the fix-bot, a fork PR does not, an occupied PR is left to its holder, and a crashed
decision goes loud. The real script runs and its real argv is asserted.

NO-SKIP POLICY: a missing prerequisite is a LOUD FAILURE, never a skip.
"""
from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
REACTOR = REPO / "scripts" / "run_failure_reactor.py"
sys.path.insert(0, str(REPO / "scripts"))
import run_failure_reactor as reactor  # noqa: E402

OWNER = "asimov-agent"


def gh_stub(tmp_path: Path, run: dict, prs: list[dict], comments: dict | None = None,
            filed: list[str] | None = None, fail_read: str | None = None,
            checks: dict | None = None, commits: dict | None = None) -> Path:
    """A `gh` that answers the shapes the reactor uses, and logs every argv.

    `run` is the `gh run view --json` object; `prs` is the REST `pull_requests` array; `comments`
    maps PR number -> its comment bodies; `filed` lists markers `issue list --search` should find;
    `fail_read` is a substring of an argv that should make `gh` exit non-zero (a crashed read);
    `checks` maps PR number -> its `gh pr checks` rows; `commits` maps PR number -> its commit
    message headlines (the fix-bot attempt counter).
    """
    bin_dir = tmp_path / "bin"; bin_dir.mkdir(exist_ok=True)
    scenario = tmp_path / "scenario.json"
    scenario.write_text(json.dumps({"run": run, "prs": prs, "comments": comments or {},
                                    "filed": filed or [], "fail_read": fail_read,
                                    "checks": checks or {}, "commits": commits or {}}))
    log = tmp_path / "gh-calls"
    log.write_text("")
    gh = bin_dir / "gh"
    gh.write_text(f"""#!/usr/bin/env python3
import json, pathlib, sys
sc = json.loads(pathlib.Path("{scenario}").read_text())
a = sys.argv[1:]
with open("{log}", "a") as fh:
    print(" ".join(x.replace("\\n", "\\\\n") for x in a), file=fh)
if sc.get("fail_read") and sc["fail_read"] in " ".join(a):
    sys.stderr.write("boom\\n"); sys.exit(1)
if a[0] == "api":
    print(json.dumps({{"pull_requests": sc["prs"]}}))
elif a[:2] == ["run", "view"]:
    if "--log-failed" in a:
        print("line1\\nline2\\nline3\\nline4\\nline5")
    else:
        print(json.dumps(sc["run"]))
elif a[:2] == ["pr", "checks"]:
    print(json.dumps(sc["checks"].get(a[2], [])))
elif a[:2] == ["pr", "view"]:
    print(json.dumps({{"comments": sc["comments"].get(a[2], []),
                      "commits": [{{"messageHeadline": m}} for m in sc["commits"].get(a[2], [])]}}))
elif a[:2] == ["pr", "comment"]:
    pass
elif a[:2] == ["workflow", "run"]:
    pass
elif a[:2] == ["issue", "list"]:
    hit = [k for k in sc["filed"] if k in " ".join(a)]
    print(json.dumps([{{"number": 1, "title": k}} for k in hit]))
elif a[:2] == ["issue", "create"]:
    print("https://github.com/asimov-agent/llgenie/issues/900")
else:
    sys.exit(f"unexpected gh call: {{a}}")
""")
    gh.chmod(gh.stat().st_mode | stat.S_IEXEC)
    return log


def run_reactor(tmp_path: Path, args: list[str]):
    env = dict(os.environ)
    env["PATH"] = f"{tmp_path / 'bin'}:{env['PATH']}"
    return subprocess.run([sys.executable, str(REACTOR), *args], cwd=str(tmp_path),
                          env=env, capture_output=True, text=True, timeout=60)


def failed_run(workflow="ci.yml", job="unit", head_sha="abcdef1234567890", event="push",
               conclusion="failure", job_id=42):
    return {"conclusion": conclusion, "headSha": head_sha, "event": event,
            "workflowName": workflow, "displayTitle": f"{workflow} run",
            "jobs": [{"name": job, "conclusion": "failure", "databaseId": job_id,
                      "steps": [{"name": "run tests", "conclusion": "failure"}]}]}


def pr(num, branch="feat/x", owner=OWNER):
    return {"number": num, "head": {"ref": branch, "repo": {"owner": {"login": owner}}},
            "title": f"PR {num}"}


RED = [{"name": "linux / unit", "state": "FAILURE", "bucket": "fail"}]


def _body_of(line: str) -> str:
    """The `--body` argument of an `issue create` log line (between `--body ` and ` --label`)."""
    start = line.index("--body ") + len("--body ")
    end = line.index(" --label", start)
    return line[start:end]


# ---------------------------------------------------------------------------
# Route B: a red run with no pushable PR files ONE deduped issue
# ---------------------------------------------------------------------------
def test_a_red_main_run_with_no_pr_files_one_issue(tmp_path):
    # Given a completed failed run on main with no pull request
    log = gh_stub(tmp_path, failed_run(), [])
    # When the reactor routes the run
    r = run_reactor(tmp_path, ["--repo", f"{OWNER}/llgenie", "--run-id", "123"])
    # Then it files exactly one issue carrying the failing job, the log tail, the marker and the label
    assert r.returncode == 0, r.stdout + r.stderr
    creates = [l for l in log.read_text().splitlines() if l.startswith("issue create")]
    assert len(creates) == 1, creates
    assert "--label" in creates[0] and "agent:implement" in creates[0]
    body = _body_of(creates[0])
    assert "ci.yml" in body and "unit" in body
    assert "line5" in body, "the log tail travels with the claim"
    assert reactor.marker("ci.yml", "unit", "abcdef1234567890") in body


def test_the_same_head_sha_again_files_nothing(tmp_path):
    # Given an OPEN issue already carrying the marker for this workflow/job@head-sha
    m = reactor.marker("ci.yml", "unit", "abcdef1234567890")
    log = gh_stub(tmp_path, failed_run(), [], filed=[m])
    # When the reactor routes the same run again
    r = run_reactor(tmp_path, ["--repo", f"{OWNER}/llgenie", "--run-id", "123"])
    # Then it files nothing and exits 0
    assert r.returncode == 0, r.stdout + r.stderr
    assert "already filed" in r.stdout
    assert not [l for l in log.read_text().splitlines() if l.startswith("issue create")]


def test_the_issue_body_carries_the_failing_job_and_log_tail(tmp_path):
    # Given a failed run with a failing job and a failing log
    log = gh_stub(tmp_path, failed_run(job="publish", job_id=7), [])
    # When the reactor files the issue
    r = run_reactor(tmp_path, ["--repo", f"{OWNER}/llgenie", "--run-id", "123"])
    # Then the body names the failing job, its step, and a tail of the failing log
    assert r.returncode == 0, r.stdout + r.stderr
    creates = [l for l in log.read_text().splitlines() if l.startswith("issue create")]
    body = _body_of(creates[0])
    assert "publish" in body and "run tests" in body
    assert "line5" in body


def test_the_file_path_writes_only_an_issue(tmp_path):
    # Given a failed run with no pushable PR
    log = gh_stub(tmp_path, failed_run(), [])
    # When the reactor routes the run
    r = run_reactor(tmp_path, ["--repo", f"{OWNER}/llgenie", "--run-id", "123"])
    # Then every gh call is a read or an issue create — never a push, commit or merge
    assert r.returncode == 0, r.stdout + r.stderr
    verbs = {l.split()[0] for l in log.read_text().splitlines()}
    assert verbs <= {"api", "run", "issue"}, verbs


# ---------------------------------------------------------------------------
# Route A: a red same-repo PR dispatches the fix-bot
# ---------------------------------------------------------------------------
def test_a_red_same_repo_pr_run_dispatches_the_fix_bot(tmp_path):
    # Given a completed failed run whose pull_requests names an open, non-draft, same-repo PR
    log = gh_stub(tmp_path, failed_run(), [pr(252)], checks={"252": RED})
    # When the reactor routes the run
    r = run_reactor(tmp_path, ["--repo", f"{OWNER}/llgenie", "--run-id", "123"])
    # Then it claims the PR and dispatches fix-bot.yml for it, and files no issue
    assert r.returncode == 0, r.stdout + r.stderr
    calls = log.read_text().splitlines()
    dispatch = [l for l in calls if l.startswith("workflow run")]
    assert len(dispatch) == 1 and "fix-bot.yml" in dispatch[0] and "pr_number=252" in dispatch[0]
    assert "branch=feat/x" in dispatch[0]
    assert not [l for l in calls if l.startswith("issue create")]
    # the claim precedes the dispatch
    claim = next((i for i, l in enumerate(calls) if l.startswith("pr comment") and "bot-claim" in l), None)
    disp = next((i for i, l in enumerate(calls) if l.startswith("workflow run")), None)
    assert claim is not None and disp is not None, calls
    assert claim < disp, f"the claim must precede the dispatch: {calls}"


def test_a_fork_pr_run_is_not_dispatched(tmp_path):
    # Given a completed failed run whose pull_requests names a PR whose head is in a fork
    log = gh_stub(tmp_path, failed_run(), [pr(1, owner="someone-else")])
    # When the reactor routes the run
    r = run_reactor(tmp_path, ["--repo", f"{OWNER}/llgenie", "--run-id", "123"])
    # Then it does not dispatch the fix-bot and reports the fork loudly
    assert r.returncode == 0, r.stdout + r.stderr
    assert "FORK" in r.stdout
    assert not [l for l in log.read_text().splitlines() if l.startswith("workflow run")]


def test_an_occupied_pr_is_left_to_its_holder(tmp_path):
    # Given a red same-repo PR whose thread carries a fresh claim from another bot
    import datetime as dt
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    claim = {"body": f"<!-- bot-claim: rebase-bot {now} rebase -->\nstarting"}
    log = gh_stub(tmp_path, failed_run(), [pr(252)], comments={"252": [claim]}, checks={"252": RED})
    # When the reactor routes the run
    r = run_reactor(tmp_path, ["--repo", f"{OWNER}/llgenie", "--run-id", "123"])
    # Then it does not dispatch the fix-bot and says the PR is claimed
    assert r.returncode == 0, r.stdout + r.stderr
    assert "claimed" in r.stdout
    assert not [l for l in log.read_text().splitlines() if l.startswith("workflow run")]


# ---------------------------------------------------------------------------
# a crashed decision goes loud
# ---------------------------------------------------------------------------
def test_a_crashed_decision_goes_loud(tmp_path):
    # Given a gh that fails a read the reactor needs
    log = gh_stub(tmp_path, failed_run(), [], fail_read="run view")
    # When the reactor routes the run
    r = run_reactor(tmp_path, ["--repo", f"{OWNER}/llgenie", "--run-id", "123"])
    # Then it prints the failure to stderr and exits non-zero
    assert r.returncode != 0, r.stdout + r.stderr
    assert "failed" in r.stderr.lower() or "boom" in r.stderr


# ---------------------------------------------------------------------------
# the workflow calls the reactor through a make target
# ---------------------------------------------------------------------------
def test_the_workflow_calls_the_reactor_through_a_make_target():
    """The route decision lives in code, not in a job `if:` (issue #107): the workflow's reactor
    step invokes `make run-failure-reactor` and carries the owner PAT (so the fix-bot dispatch
    carries the owner identity, and the issue it files is labelled for the issue-bot)."""
    import yaml
    wf = yaml.safe_load((REPO / ".github" / "workflows" / "run-failure-reactor.yml").read_text())
    steps = {s.get("name"): s for s in wf["jobs"]["react"]["steps"]}
    reactor_step = steps["Route the failed run to a fix or a deduped issue"]
    assert "make run-failure-reactor" in reactor_step["run"]
    assert reactor_step.get("env", {}).get("GH_TOKEN"), reactor_step
    assert reactor_step["env"]["GH_TOKEN"] == "${{ secrets.BUMP_TOKEN }}"
    assert "RUN_ID" in reactor_step["env"] and "REPO" in reactor_step["env"]
