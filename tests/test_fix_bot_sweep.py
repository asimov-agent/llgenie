"""Which PR the fix-bot sweep picks, and what it refuses (issue #222).

The sweep decides through `gh`, which is stubbed on PATH here (the repo's allowance for an
external CLI), so the *decision logic* runs for real against controlled API answers: fork and
draft PRs, `main`, green PRs and branches already at the attempt cap are refused with a reason,
and only a genuinely red same-repo PR is dispatched — with the argv the workflow needs.
"""
from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SWEEP = REPO / "scripts" / "fix_bot_sweep.py"
from scripts import fix_bot_sweep as sweep

OWNER = "asimov-agent"


def gh_stub(tmp_path: Path, prs, checks: dict, commits: dict, comments: dict | None = None,
            no_checks: list | None = None) -> Path:
    """A `gh` that answers the three shapes the sweep uses, and logs a dispatch."""
    bin_dir = tmp_path / "bin"; bin_dir.mkdir(exist_ok=True)
    scenario = tmp_path / "scenario.json"
    scenario.write_text(json.dumps({"prs": prs, "checks": checks, "commits": commits,
                                    "comments": comments or {},
                                    "no_checks": no_checks or []}))
    log = tmp_path / "gh-calls"
    log.write_text("")
    gh = bin_dir / "gh"
    gh.write_text(f"""#!/usr/bin/env python3
import json, os, pathlib, sys
sc = json.loads(pathlib.Path("{scenario}").read_text())
a = sys.argv[1:]
with open("{log}", "a") as fh:
    print(" ".join(a), file=fh)
if a[:2] == ["pr", "list"]:
    print(json.dumps(sc["prs"]))
elif a[:2] == ["pr", "checks"]:
    if a[2] in (sc.get("no_checks") or []):
        # What GitHub answers for a branch whose workflows never ran (issue #496): non-zero, and this
        # message on stderr, with nothing on stdout.
        sys.stderr.write("no checks reported on the 'agent/x' branch")
        sys.exit(1)
    print(json.dumps(sc["checks"].get(a[2], [])))
elif a[:2] == ["pr", "view"]:
    print(json.dumps({{"commits": [{{"messageHeadline": m}} for m in sc["commits"].get(a[2], [])],
                      "comments": sc.get("comments", {{}}).get(a[2], [])}}))
elif a[:2] == ["pr", "comment"]:
    pass
elif a[:2] == ["workflow", "run"]:
    pass
else:
    sys.exit(f"unexpected gh call: {{a}}")
""")
    gh.chmod(gh.stat().st_mode | stat.S_IEXEC)
    return log


def run_sweep(tmp_path: Path, args: list[str]):
    env = dict(os.environ)
    env["PATH"] = f"{tmp_path / 'bin'}:{env['PATH']}"
    return subprocess.run([sys.executable, str(SWEEP), *args], cwd=str(tmp_path),
                          env=env, capture_output=True, text=True, timeout=60)


def pr(num, branch="feat/x", owner=OWNER, draft=False, updated="2026-10-14T01:00:00Z"):
    return {"number": num, "title": f"PR {num}", "isDraft": draft, "headRefName": branch,
            "headRepositoryOwner": {"login": owner}, "updatedAt": updated}


RED = [{"name": "linux / unit", "state": "FAILURE", "bucket": "fail"}]
GREEN = [{"name": "linux / unit", "state": "SUCCESS", "bucket": "pass"}]


def test_a_red_same_repo_pr_is_chosen_and_dispatched(tmp_path):
    log = gh_stub(tmp_path, [pr(252)], {"252": RED}, {"252": []})
    r = run_sweep(tmp_path, ["--repo", f"{OWNER}/llgenie"])
    assert r.returncode == 0, r.stdout + r.stderr
    assert "252" in r.stdout and "dispatched the fix-bot" in r.stdout
    dispatch = [l for l in log.read_text().splitlines() if l.startswith("workflow run")]
    assert len(dispatch) == 1 and "pr_number=252" in dispatch[0] and "branch=feat/x" in dispatch[0]
    assert "rounds=5" in dispatch[0] and "fix-bot.yml" in dispatch[0]


def test_a_fork_draft_or_main_pr_is_refused_with_a_reason(tmp_path):
    gh_stub(tmp_path, [pr(1, owner="someone-else"), pr(2, draft=True), pr(3, branch="main")],
            {"1": RED, "2": RED, "3": RED}, {})
    r = run_sweep(tmp_path, ["--repo", f"{OWNER}/llgenie"])
    assert r.returncode == 0
    assert "nothing to fix" in r.stdout
    assert "a fork (someone-else)" in r.stdout and "draft" in r.stdout and "the base branch" in r.stdout


def test_a_green_pr_is_refused(tmp_path):
    gh_stub(tmp_path, [pr(10)], {"10": GREEN}, {"10": []})
    r = run_sweep(tmp_path, ["--repo", f"{OWNER}/llgenie"])
    assert "no failing check" in r.stdout and "nothing to fix" in r.stdout


def test_the_attempt_cap_is_respected_and_reported(tmp_path):
    """Three `fix(bot):` commits already on the branch: the bot does not run again."""
    gh_stub(tmp_path, [pr(11)], {"11": RED}, {"11": ["fix(bot): one", "fix(bot): two", "fix(bot): three"]})
    r = run_sweep(tmp_path, ["--repo", f"{OWNER}/llgenie", "--max-attempts", "3"])
    assert "the cap (3/3 attempts)" in r.stdout and "nothing to fix" in r.stdout


def test_the_oldest_updated_red_pr_wins(tmp_path):
    """One PR per sweep: the oldest-updated red PR is repaired, and the sweep stops there."""
    log = gh_stub(tmp_path, [pr(20, updated="2026-10-14T05:00:00Z"), pr(21, updated="2026-10-14T02:00:00Z")],
                  {"20": RED, "21": RED}, {})
    r = run_sweep(tmp_path, ["--repo", f"{OWNER}/llgenie"])
    assert "dispatched the fix-bot for #21" in r.stdout
    dispatches = [l for l in log.read_text().splitlines() if l.startswith("workflow run")]
    assert len(dispatches) == 1, "one dispatch per sweep"
    assert "pr_number=20" not in dispatches[0], "the newer red PR waits for the next sweep"


def test_dry_run_dispatches_nothing(tmp_path):
    log = gh_stub(tmp_path, [pr(30)], {"30": RED}, {})
    r = run_sweep(tmp_path, ["--repo", f"{OWNER}/llgenie", "--dry"])
    assert "--dry: nothing dispatched" in r.stdout
    assert not [l for l in log.read_text().splitlines() if l.startswith("workflow run")]


def test_the_attempt_counter_only_counts_the_bot(tmp_path, monkeypatch):
    gh_stub(tmp_path, [pr(40)], {"40": RED},
            {"40": ["feat: mine", "fix(bot): a", "docs: theirs", "fix(bot): b"]})
    monkeypatch.setenv("PATH", f"{tmp_path / 'bin'}:{os.environ['PATH']}")
    assert sweep.bot_attempts(f"{OWNER}/llgenie", 40) == 2


def test_the_cap_is_a_parameter(tmp_path):
    gh_stub(tmp_path, [pr(50)], {"50": RED}, {"50": ["fix(bot): a"]})
    r = run_sweep(tmp_path, ["--repo", f"{OWNER}/llgenie", "--max-attempts", "1"])
    assert "the cap (1/1 attempts)" in r.stdout


def test_a_pr_with_no_checks_does_not_kill_the_sweep(tmp_path):
    """A branch whose workflows never ran is not a red PR: `gh pr checks` exits non-zero (#496).

    Measured on PR #527 (`app/github-actions`, opened with the job token): the sweep died with
    `RuntimeError: gh pr checks 527 … no checks reported` before it could look at any other PR.
    """

    # Given one open PR whose branch has no checks at all
    log = gh_stub(tmp_path, [pr(527, "agent/architecture-x")], checks={}, commits={},
                  no_checks=["527"])

    # When  the sweep runs
    r = run_sweep(tmp_path, ["--repo", f"{OWNER}/llgenie"])

    # Then  it exits cleanly, having read the checks and picked nothing
    assert r.returncode == 0, f"sweep exited {r.returncode}: {r.stderr[-400:]}"
    assert "pr checks 527" in log.read_text()
    assert "no failing check" in r.stdout, r.stdout[-400:]
    assert "nothing to fix" in r.stdout, r.stdout[-400:]


# ---- the claim protocol on the fix-bot's side (issue #279) ----

def _claim(at, work="fix", bot="fix-bot"):
    return {"body": f"<!-- bot-claim: {bot} {at} {work} -->\nstarting"}


def test_an_occupied_pr_is_skipped_and_the_next_red_one_is_taken(tmp_path):
    """A recent comment without a `done` means someone is on that PR: skip it, take the next one."""
    import datetime as dt
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    red = [{"number": 21, "title": "one", "isDraft": False, "updatedAt": "2026-10-01T00:00:00Z",
            "headRefName": "b1", "mergeStateStatus": "CLEAN"},
           {"number": 22, "title": "two", "isDraft": False, "updatedAt": "2026-10-02T00:00:00Z",
            "headRefName": "b2", "mergeStateStatus": "CLEAN"}]
    log = gh_stub(tmp_path, red, checks={"21": [{"name": "unit", "state": "failure", "bucket": "fail"}],
                     "22": [{"name": "unit", "state": "failure", "bucket": "fail"}]}, commits={},
                  comments={"21": [_claim(now, "rebase", bot="rebase-bot")]})
    r = run_sweep(tmp_path, ["--repo", f"{OWNER}/llgenie"])
    calls = log.read_text()
    assert r.returncode == 0, f"sweep exited {r.returncode}: {r.stderr[-400:]}"
    # it read #21's comments, left it alone, and claimed the one it took
    assert "pr comment 21" not in calls, "an occupied PR must not be claimed"
    assert "pr comment 22" in calls, "the picked PR must be claimed before the loop runs"


def test_the_sweep_claims_the_pr_before_it_dispatches_the_loop(tmp_path):
    """Issue #279: the repair is invisible for up to 180 minutes (no commit, nothing in flight), so
    the claim on the PR is the only thing the rebase-bot can see. It has to be posted BEFORE the
    dispatch, or the window it exists to close stays open."""
    red = [{"number": 21, "title": "one", "isDraft": False, "updatedAt": "2026-10-01T00:00:00Z",
            "headRefName": "b1", "mergeStateStatus": "CLEAN"}]
    log = gh_stub(tmp_path, red, checks={"21": [{"name": "unit", "state": "failure", "bucket": "fail"}]}, commits={})
    run_sweep(tmp_path, ["--repo", f"{OWNER}/llgenie"])
    calls = log.read_text().splitlines()
    claim = next((i for i, l in enumerate(calls) if l.startswith("pr comment 21") and "bot-claim" in l), None)
    dispatch = next((i for i, l in enumerate(calls) if l.startswith("workflow run")), None)
    assert claim is not None and dispatch is not None, calls
    assert claim < dispatch, f"the claim must precede the dispatch: {calls}"
    assert "fix-bot" in calls[claim] and " fix " in calls[claim], calls[claim]


def test_the_sweep_does_not_claim_when_it_dry_runs(tmp_path):
    red = [{"number": 21, "title": "one", "isDraft": False, "updatedAt": "2026-10-01T00:00:00Z",
            "headRefName": "b1", "mergeStateStatus": "CLEAN"}]
    log = gh_stub(tmp_path, red, checks={"21": [{"name": "unit", "state": "failure", "bucket": "fail"}]}, commits={})
    run_sweep(tmp_path, ["--repo", f"{OWNER}/llgenie", "--dry"])
    assert "pr comment" not in log.read_text(), "a dry run must not claim anything"


# ------------------------------------------- the repository's own fork (issue #340)


def test_a_pr_on_the_allowlisted_fork_is_chosen(tmp_path):
    """Every llgenie PR comes from the fork; with --own-fork the sweep must take it."""
    log = gh_stub(tmp_path, [pr(253, owner="andyholst")], {"253": RED}, {"253": []})
    r = run_sweep(tmp_path, ["--repo", f"{OWNER}/llgenie", "--own-fork", "andyholst"])
    assert r.returncode == 0, r.stdout + r.stderr
    assert "dispatched the fix-bot" in r.stdout and "253" in r.stdout
    dispatch = [l for l in log.read_text().splitlines() if l.startswith("workflow run")]
    assert len(dispatch) == 1 and "pr_number=253" in dispatch[0]


def test_another_fork_is_still_skipped(tmp_path):
    """A fork this bot cannot push to stays out, even with an allowlist."""
    log = gh_stub(tmp_path, [pr(254, owner="stranger")], {"254": RED}, {"254": []})
    r = run_sweep(tmp_path, ["--repo", f"{OWNER}/llgenie", "--own-fork", "andyholst"])
    assert r.returncode == 0, r.stdout + r.stderr
    assert "nothing to fix" in r.stdout
    assert "a fork (stranger)" in r.stdout
    assert not [l for l in log.read_text().splitlines() if l.startswith("workflow run")]


def test_the_repair_pushes_to_the_pr_head_remote():
    """The workflow checks the branch out from its head remote and pushes there."""
    wf = (REPO / ".github" / "workflows" / "fix-bot.yml").read_text()

    # The decision is told which fork it may push to
    assert "OWN_FORK=andyholst" in wf

    # The resolve step records the head repository the push has to target
    assert "headrepo=$headrepo" in wf

    # The branch is fetched from that remote, and the push uses it rather than a blind `origin`
    assert "git fetch fork \"$BRANCH\"" in wf
    assert 'echo "REMOTE=fork" >> "$GITHUB_ENV"' in wf
    assert 'git push --force-with-lease "${REMOTE:-origin}"' in wf


# ---- re-triggered by a failed CI run (issue #538) ----

def test_a_failed_run_repairs_its_own_pr_with_five_attempts(tmp_path):
    """A `workflow_run` names the PR: repair THAT one, not the oldest eligible, up to 5 attempts."""

    # Given two red same-repo PRs, the OLDEST one first by updatedAt
    older = pr(21, "b1", updated="2026-10-01T00:00:00Z")
    newer = pr(22, "b2", updated="2026-10-05T00:00:00Z")
    log = gh_stub(tmp_path, [older, newer],
                  checks={"21": RED, "22": RED}, commits={})

    # When  the sweep is pointed at #22 (the PR the failed run belonged to)
    r = run_sweep(tmp_path, ["--repo", f"{OWNER}/llgenie", "--pr", "22", "--max-attempts", "5"])

    # Then  it dispatches #22 only, with 5 rounds
    calls = log.read_text()
    dispatch = [l for l in calls.splitlines() if l.startswith("workflow run")]
    assert r.returncode == 0, r.stdout + r.stderr
    assert len(dispatch) == 1, dispatch
    assert "pr_number=22" in dispatch[0], dispatch
    assert "rounds=5" in dispatch[0], dispatch
    assert "pr_number=21" not in dispatch[0]


def test_a_workflow_run_trigger_is_wired_to_the_ci_workflow():
    """The bot is woken by the failure it repairs, and its own default is five attempts."""

    wf = (REPO / ".github" / "workflows" / "fix-bot.yml").read_text()

    assert "workflow_run:" in wf and 'workflows: ["CI"]' in wf, "CI failures must wake the bot"
    assert "conclusion == 'failure'" in wf, "only a failed run may dispatch a repair"
    assert "ATTEMPTS=5" in wf, "the sweep cap is five"
    assert 'default: "5"' in wf, "a manual dispatch defaults to five rounds"


# ---------------------------------------------------------------------------------------------------
# A cancellation is not a verdict (issue #843): `gh pr checks` buckets CANCELLED as `fail`, so before
# this the sweep "fixed" PRs whose only problem was that a bulk cancel killed their run.
def test_a_cancelled_check_is_pending_not_red(monkeypatch, capsys):
    rows = [{"name": "linux / unit", "state": "CANCELLED", "bucket": "fail", "workflow": "CI"},
            {"name": "guard", "state": "CANCELLED", "bucket": "cancel", "workflow": "CI"}]
    monkeypatch.setattr(sweep, "_gh", lambda args: json.dumps(rows))

    assert sweep.failing_checks(OWNER + "/llgenie", 7) == []
    out = capsys.readouterr().out
    assert "PENDING, not red" in out, out
    assert "ci-requeue-cancelled" in out, out


def test_a_real_failure_is_still_red_beside_a_cancelled_check(monkeypatch):
    rows = [{"name": "linux / unit", "state": "FAILURE", "bucket": "fail", "workflow": "CI"},
            {"name": "docs", "state": "CANCELLED", "bucket": "fail", "workflow": "Docs"}]
    monkeypatch.setattr(sweep, "_gh", lambda args: json.dumps(rows))

    assert sweep.failing_checks(OWNER + "/llgenie", 7) == ["linux / unit"]
