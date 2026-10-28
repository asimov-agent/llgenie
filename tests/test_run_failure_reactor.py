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
from scripts import run_failure_reactor as reactor

OWNER = "asimov-agent"


def gh_stub(tmp_path: Path, run: dict, prs: list[dict], comments: dict | None = None,
            filed: list[str] | None = None, fail_read: str | None = None,
            checks: dict | None = None, commits: dict | None = None,
            rest: dict | None = None, fork_prs: dict | None = None,
            pr_meta: dict | None = None, newer_runs: list[dict] | None = None) -> Path:
    """A `gh` that answers the shapes the reactor uses, and logs every argv.

    `run` is the `gh run view --json` object; `prs` is the REST `pull_requests` array; `comments`
    maps PR number -> its comment bodies; `filed` lists markers `issue list --search` should find;
    `fail_read` is a substring of an argv that should make `gh` exit non-zero (a crashed read);
    `checks` maps PR number -> its `gh pr checks` rows; `commits` maps PR number -> its commit
    message headlines (the fix-bot attempt counter); `newer_runs` is the branch's `gh run list`
    answer, which is what decides whether a failure was superseded (issue #565).
    """
    bin_dir = tmp_path / "bin"; bin_dir.mkdir(exist_ok=True)
    scenario = tmp_path / "scenario.json"
    scenario.write_text(json.dumps({"run": run, "prs": prs, "comments": comments or {},
                                    "filed": filed or [], "fail_read": fail_read,
                                    "checks": checks or {}, "commits": commits or {},
                                    "rest": rest or {}, "fork_prs": fork_prs or {},
                                    "pr_meta": pr_meta or {}, "newer_runs": newer_runs or []}))
    log = tmp_path / "gh-calls"
    log.write_text("")
    gh = bin_dir / "gh"
    gh.write_text(f"""#!/usr/bin/env python3
import json, pathlib, sys
sc = json.loads(pathlib.Path("{scenario}").read_text())
a = sys.argv[1:]
import os
with open("{log}", "a") as fh:
    # the token `gh` was handed: the dispatch identity is asserted from here (issue #555)
    print(" ".join(x.replace("\\n", "\\\\n") for x in a) + " | token=" + os.environ.get("GH_TOKEN", ""), file=fh)
if sc.get("fail_read") and sc["fail_read"] in " ".join(a):
    sys.stderr.write("boom\\n"); sys.exit(1)
if a[0] == "api":
    rest = dict(sc["rest"] or {{"pull_requests": sc["prs"]}})
    rest.setdefault("pull_requests", sc["prs"])
    print(json.dumps(rest))
elif a[:2] == ["run", "view"]:
    if "--log-failed" in a:
        print("line1\\nline2\\nline3\\nline4\\nline5")
    else:
        print(json.dumps(sc["run"]))
elif a[:2] == ["run", "list"]:
    print(json.dumps(sc["newer_runs"]))
elif a[:2] == ["pr", "checks"]:
    print(json.dumps(sc["checks"].get(a[2], [])))
elif a[:2] == ["pr", "list"]:
    rows = sc["fork_prs"]
    for branch, nums in rows.items():
        if any(branch in x for x in a):
            for n in nums:
                print(n)
elif a[:2] == ["pr", "view"]:
    meta = sc["pr_meta"].get(a[2], {{}})
    print(json.dumps({{**meta, "comments": sc["comments"].get(a[2], []),
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


#: The owner identity a dispatch must carry (fix-bot's guard refuses `github-actions[bot]`, #510).
OWNER_TOKEN = "ghp_owner_token_for_tests"


def run_reactor(tmp_path: Path, args: list[str], dispatch_token: str | None = OWNER_TOKEN):
    env = dict(os.environ)
    env["PATH"] = f"{tmp_path / 'bin'}:{env['PATH']}"
    env.pop("DISPATCH_TOKEN", None)
    if dispatch_token is not None:
        env["DISPATCH_TOKEN"] = dispatch_token
    return subprocess.run([sys.executable, str(REACTOR), *args], cwd=str(tmp_path),
                          env=env, capture_output=True, text=True, timeout=60)


def failed_run(workflow="ci.yml", job="unit", head_sha="abcdef1234567890", event="push",
               conclusion="failure", job_id=42, created_at=""):
    return {"conclusion": conclusion, "headSha": head_sha, "event": event,
            "workflowName": workflow, "displayTitle": f"{workflow} run",
            "createdAt": created_at,
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
    step invokes `make run-failure-reactor`.

    The credential is `github.token`, not the owner PAT (issue #412): the step files ONE issue and
    dispatches the fix-bot, which need `issues: write` + `actions: write` — both declared by this
    workflow — while `secrets.BUMP_TOKEN` carries neither (it is the push credential). Handing the
    PAT to this step made every dispatch `HTTP 403 … Resource not accessible by personal access
    token`.
    """
    import yaml
    wf = yaml.safe_load((REPO / ".github" / "workflows" / "run-failure-reactor.yml").read_text())
    steps = {s.get("name"): s for s in wf["jobs"]["react"]["steps"]}
    reactor_step = steps["Route the failed run to a fix or a deduped issue"]
    assert "make run-failure-reactor" in reactor_step["run"]
    assert reactor_step.get("env", {}).get("GH_TOKEN"), reactor_step
    assert reactor_step["env"]["GH_TOKEN"] == "${{ github.token }}", (
        "the issue/dispatch writes need the repository-scoped token (issue #412)"
    )
    perms = wf["permissions"]
    assert perms["issues"] == "write" and perms["actions"] == "write", perms
    assert "RUN_ID" in reactor_step["env"] and "REPO" in reactor_step["env"]


# ---------------------------------------------------------------------------
# Route A for a FORK-head run: the PR is resolved from the run itself (issue #555)
# ---------------------------------------------------------------------------
def _fork_rest(branch="feat/x", owner=None):
    """The REST run object a fork `pull_request` run returns: NO pull_requests, but a head."""
    return {"pull_requests": [], "head_branch": branch,
            "head_repository": {"owner": {"login": owner or reactor.TRUSTED_FORK}}}


def _open_pr_meta(num, branch="feat/x", owner=None, draft=False):
    return {str(num): {"number": num, "title": f"PR {num}", "headRefName": branch,
                       "headRepositoryOwner": {"login": owner or reactor.TRUSTED_FORK},
                       "isDraft": draft, "state": "OPEN", "updatedAt": ""}}


def test_a_red_fork_pr_run_dispatches_the_fix_bot_as_the_owner(tmp_path):
    """Every agent PR lives in the fork; a red run on it must be repaired, not filed as an issue."""

    # Given a fork run (empty pull_requests) whose head resolves to an open, red, non-draft PR
    log = gh_stub(tmp_path, failed_run(event="pull_request"), [], rest=_fork_rest(),
                  fork_prs={"feat/x": [260]}, checks={"260": RED},
                  pr_meta=_open_pr_meta(260))

    # When the reactor routes the run
    r = run_reactor(tmp_path, ["--repo", f"{OWNER}/llgenie", "--run-id", "123"])

    # Then it claims that PR and dispatches the fix-bot for it, and files no issue
    assert r.returncode == 0, r.stdout + r.stderr
    calls = log.read_text().splitlines()
    dispatch = [l for l in calls if l.startswith("workflow run")]
    assert len(dispatch) == 1 and "pr_number=260" in dispatch[0], calls
    assert "branch=feat/x" in dispatch[0], dispatch[0]
    assert not [l for l in calls if l.startswith("issue create")], calls

    # And   the dispatch carries the OWNER identity, never the job token (fix-bot's guard refuses
    #       github-actions[bot]: run 39917926028)
    assert f"token={OWNER_TOKEN}" in dispatch[0], dispatch[0]


def test_a_missing_dispatch_token_is_loud_and_dispatches_nothing(tmp_path):
    """A dispatch as `github-actions[bot]` would be refused by the guard: refuse to make it at all."""

    # Given the same red fork PR, but no DISPATCH_TOKEN in the environment
    log = gh_stub(tmp_path, failed_run(event="pull_request"), [], rest=_fork_rest(),
                  fork_prs={"feat/x": [260]}, checks={"260": RED},
                  pr_meta=_open_pr_meta(260))

    # When  the reactor routes the run
    r = run_reactor(tmp_path, ["--repo", f"{OWNER}/llgenie", "--run-id", "123"],
                    dispatch_token=None)

    # Then  it fails loudly, naming the variable, and neither dispatches nor files anything
    assert r.returncode == 1, r.stdout + r.stderr
    assert "DISPATCH_TOKEN" in r.stderr, r.stderr
    calls = log.read_text().splitlines()
    assert not [l for l in calls if l.startswith("workflow run")], calls
    assert not [l for l in calls if l.startswith("issue create")], calls


def test_a_fifth_party_fork_run_is_not_dispatched(tmp_path):
    """A stranger's fork cannot be pushed by any token we hold: report it, and file the issue."""

    # Given a run whose head lives in someone else's fork
    log = gh_stub(tmp_path, failed_run(event="pull_request"), [],
                  rest=_fork_rest(owner="stranger"))

    # When  the reactor routes the run
    r = run_reactor(tmp_path, ["--repo", f"{OWNER}/llgenie", "--run-id", "123"])

    # Then  it does not dispatch, says why, and falls back to the deduped issue
    assert r.returncode == 0, r.stdout + r.stderr
    assert "FIFTH-PARTY" in r.stdout, r.stdout
    calls = log.read_text().splitlines()
    assert not [l for l in calls if l.startswith("workflow run")], calls
    assert len([l for l in calls if l.startswith("issue create")]) == 1, calls


def test_a_draft_fork_pr_run_files_an_issue_instead(tmp_path):
    """Draft means the author is still working: the fix-bot's own rules refuse it, so do we."""

    # Given a fork run whose PR is still a draft
    log = gh_stub(tmp_path, failed_run(event="pull_request"), [], rest=_fork_rest(),
                  fork_prs={"feat/x": [260]}, checks={"260": RED},
                  pr_meta=_open_pr_meta(260, draft=True))

    # When  the reactor routes the run
    r = run_reactor(tmp_path, ["--repo", f"{OWNER}/llgenie", "--run-id", "123"])

    # Then  the sweep's own rule is the one that refuses it, and the issue path still runs
    assert r.returncode == 0, r.stdout + r.stderr
    assert "not eligible: draft" in r.stdout, r.stdout
    # And   an OPEN PR is live work: the superseded rule must not fire on it (issue #565)
    assert "SUPERSEDED" not in r.stdout, r.stdout
    calls = log.read_text().splitlines()
    assert not [l for l in calls if l.startswith("workflow run")], calls
    assert len([l for l in calls if l.startswith("issue create")]) == 1, calls


# ---------------------------------------------------------------------------
# Route B files only work that is STILL work (issue #565)
# ---------------------------------------------------------------------------
def _main_rest(branch="main"):
    """The REST run object a `push` run on a branch returns."""
    return {"pull_requests": [], "head_branch": branch}


def _run_row(conclusion, created_at, database_id=2):
    return {"databaseId": database_id, "conclusion": conclusion, "createdAt": created_at}


def test_a_merged_pr_run_files_nothing(tmp_path):
    """The branch a red run tested is merged and deleted: there is nothing left to repair."""

    # Given a failed pull_request run whose head has NO open PR any more (merged, branch gone)
    log = gh_stub(tmp_path, failed_run(event="pull_request", created_at="2026-10-23T09:39:04Z"),
                  [], rest=_fork_rest("feat/issue-bot-duplicate-sweep"), fork_prs={})

    # When  the reactor routes the run
    r = run_reactor(tmp_path, ["--repo", f"{OWNER}/llgenie", "--run-id", "123"])

    # Then  it says so and files nothing — the defect was fixed before the issue could exist
    assert r.returncode == 0, r.stdout + r.stderr
    assert "is SUPERSEDED" in r.stdout, r.stdout
    assert "merged or closed" in r.stdout, r.stdout
    calls = log.read_text().splitlines()
    assert not [l for l in calls if l.startswith("issue create")], calls


def test_a_superseded_main_push_files_nothing(tmp_path):
    """A later green run of the same workflow on the same branch is proof the failure is history."""

    # Given a red push run on main and a LATER CI run on main that concluded success
    log = gh_stub(tmp_path, failed_run(created_at="2026-10-23T07:47:17Z"), [],
                  rest=_main_rest(),
                  newer_runs=[_run_row("success", "2026-10-23T10:19:00Z"),
                              _run_row("failure", "2026-10-23T07:47:17Z", 1)])

    # When  the reactor routes the run
    r = run_reactor(tmp_path, ["--repo", f"{OWNER}/llgenie", "--run-id", "123"])

    # Then  it names the reason and files nothing
    assert r.returncode == 0, r.stdout + r.stderr
    assert "is SUPERSEDED" in r.stdout and "succeeded at" in r.stdout, r.stdout
    calls = log.read_text().splitlines()
    assert not [l for l in calls if l.startswith("issue create")], calls


def test_a_later_failure_does_not_supersede_an_earlier_one(tmp_path):
    """main still red is still work: only a LATER success retires the failure."""

    # Given a red push run on main and only a later FAILURE on the same branch
    log = gh_stub(tmp_path, failed_run(created_at="2026-10-23T07:47:17Z"), [],
                  rest=_main_rest(),
                  newer_runs=[_run_row("failure", "2026-10-23T10:19:00Z")])

    # When  the reactor routes the run
    r = run_reactor(tmp_path, ["--repo", f"{OWNER}/llgenie", "--run-id", "123"])

    # Then  it files the work item
    assert r.returncode == 0, r.stdout + r.stderr
    assert "SUPERSEDED" not in r.stdout, r.stdout
    calls = log.read_text().splitlines()
    assert len([l for l in calls if l.startswith("issue create")]) == 1, calls


def test_an_unreadable_run_list_is_not_a_supersede(tmp_path):
    """An UNKNOWN is not a verdict: a failed read must never drop a real failure (issue #312)."""

    # Given a red push run on main whose run-list read fails
    log = gh_stub(tmp_path, failed_run(created_at="2026-10-23T07:47:17Z"), [],
                  rest=_main_rest(), fail_read="run list")

    # When  the reactor routes the run
    r = run_reactor(tmp_path, ["--repo", f"{OWNER}/llgenie", "--run-id", "123"])

    # Then  it says the read failed, does not claim SUPERSEDED, and files the work item
    assert r.returncode == 0, r.stdout + r.stderr
    assert "could not be read" in r.stdout, r.stdout
    assert "SUPERSEDED" not in r.stdout, r.stdout
    calls = log.read_text().splitlines()
    assert len([l for l in calls if l.startswith("issue create")]) == 1, calls


# ---------------------------------------------------------------------------
# A cancellation is not an answer (issue #843)
# ---------------------------------------------------------------------------
def test_a_cancelled_run_with_no_later_run_is_reported_pending(tmp_path):
    """A bulk cancel kills a run mid-flight; the reactor must not read that as "nothing to do"."""

    # Given a CANCELLED run whose branch has no later run of the same workflow
    log = gh_stub(tmp_path, failed_run(conclusion="cancelled", created_at="2026-10-28T15:00:00Z"), [],
                  rest=_main_rest(), newer_runs=[])

    # When  the reactor routes it
    r = run_reactor(tmp_path, ["--repo", f"{OWNER}/llgenie", "--run-id", "123"])

    # Then  it says the verdict is still owed, and names the target that re-runs it
    assert r.returncode == 0, r.stdout + r.stderr
    assert "CANCELLED with no later run" in r.stdout, r.stdout
    assert "PENDING, not a verdict" in r.stdout, r.stdout
    assert "make ci-requeue-cancelled" in r.stdout, r.stdout
    # And nothing was filed or dispatched for it
    calls = log.read_text().splitlines()
    assert not [c for c in calls if c.startswith("issue create")], calls
    assert not [c for c in calls if "workflow run" in c], calls


def test_a_cancelled_run_a_later_run_took_over_is_superseded(tmp_path):
    """`cancel-in-progress` kills the PREVIOUS run: a later run of the same workflow owns the verdict."""

    # Given a cancelled run and a LATER run of the same workflow on the same branch
    log = gh_stub(tmp_path, failed_run(conclusion="cancelled", created_at="2026-10-28T15:00:00Z"), [],
                  rest=_main_rest(),
                  newer_runs=[_run_row("success", "2026-10-28T15:20:00Z")])

    # When  the reactor routes it
    r = run_reactor(tmp_path, ["--repo", f"{OWNER}/llgenie", "--run-id", "123"])

    # Then  it is reported as superseded with the time the later run took over, and nothing is filed
    assert r.returncode == 0, r.stdout + r.stderr
    assert "took over at 2026-10-28T15:20:00Z" in r.stdout, r.stdout
    assert "superseded, nothing to do" in r.stdout, r.stdout
    assert not [c for c in log.read_text().splitlines() if c.startswith("issue create")]
