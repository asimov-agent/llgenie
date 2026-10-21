"""The rebase bot: which PR it picks, and what it does to that PR (issue #246).

Two halves, both real code under test:

  * the SWEEP (scripts/rebase_bot_sweep.py) decides which ONE PR needs rebasing, driven through a
    fake `gh` that records argv, so the assertions are about the exact requests it makes;
  * the ACTOR (scripts/rebase_bot.sh) is driven against a real scratch git repository with two
    conflicting branches and a stub agent, so the rebase, the conflict hand-off, the structural
    gates and the force-with-lease push are exercised for real — only the LLM is a stand-in.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import rebase_bot_sweep as rb  # noqa: E402

OWNER, NAME = "asimov-agent", "llgenie"


# ------------------------------------------------------------------------------------- sweep
def _fake_gh(tmp_path: Path, opts: dict | None = None):
    opts = opts or {}
    tmp_path.mkdir(parents=True, exist_ok=True)
    log = tmp_path / "gh.log"
    # the fixtures go to disk as JSON and the stub reads them: embedding json.dumps() inside
    # generated Python source writes `false`/`true` literals, which are not Python.
    (tmp_path / "search.json").write_text(json.dumps(opts.get("search", [])))
    (tmp_path / "prs.json").write_text(json.dumps(opts.get("prs", [])))
    (tmp_path / "checks.json").write_text(json.dumps(opts.get("checks_by_pr", {})))
    (tmp_path / "comments.json").write_text(json.dumps(opts.get("comments_by_pr", {})))
    (tmp_path / "states.json").write_text(json.dumps(opts.get("states_by_pr", {})))
    gh = tmp_path / "gh"
    gh.write_text(f'''#!{sys.executable}
import json, sys, pathlib
args = sys.argv[1:]
here = pathlib.Path(__file__).parent
with open({str(log)!r}, "a") as fh:
    fh.write(json.dumps(args) + "\\n")
if args[:2] == ["search", "prs"]:
    fields = args[args.index("--json") + 1] if "--json" in args else ""
    if any(f.strip() == "comments" for f in fields.split(",")):
        sys.stderr.write('Unknown JSON field: \"comments\"\\n')
        sys.exit(1)                      # exactly what the real `gh search prs` does (#309)
    print((here / "search.json").read_text())
elif args[:2] == ["pr", "list"]:
    print((here / "prs.json").read_text())
elif args[:2] == ["pr", "view"]:
    fields = args[args.index("--json") + 1] if "--json" in args else ""
    if "mergeStateStatus" in fields:
        f = here / "states.json"
        by_pr = json.loads(f.read_text()) if f.exists() else {{}}
        seq = by_pr.get(args[2], [])
        state = seq.pop(0) if seq else "UNKNOWN"      # a sequence models the lazy computation
        by_pr[args[2]] = seq
        f.write_text(json.dumps(by_pr))
        print(json.dumps({{"mergeStateStatus": state}}))
    else:
        f = here / "comments.json"
        by_pr = json.loads(f.read_text()) if f.exists() else {{}}
        print(json.dumps({{"comments": by_pr.get(args[2], [])}}))
elif args[:2] == ["pr", "checks"]:
    f = here / "checks.json"
    by_pr = json.loads(f.read_text()) if f.exists() else {{}}
    states = by_pr.get(args[2], [])
    print(json.dumps([{{"state": s}} for s in states]))
else:
    print("")
''')
    gh.chmod(0o755)
    return gh, log


def _pr(num, state="BEHIND", *, draft=False, head="andyholst", repo=None, base="main",
        created="2026-10-01T00:00:00Z", title=None):
    return {"number": num, "title": title or f"PR {num}", "isDraft": draft,
            "mergeStateStatus": state, "headRefName": f"feat/{num}",
            "headRepositoryOwner": {"login": head}, "createdAt": created, "baseRefName": base}


def _marker_today(num, today="2026-10-14"):
    """A PR this bot already rebased today: `search prs` names it, its COMMENTS carry the marker.

    `gh search prs` has no comment bodies (issue #309), so the search row is only the number and
    the marker comes from `comments_by_pr` — the two-call shape the real CLI has.
    """
    return {"number": num}


def _marker_comments(nums, today="2026-10-14"):
    """The `comments_by_pr` fixture carrying this bot's `rebased` DONE marker for `today`.

    The real marker shape matters: `rebased_today` reads `bot_claims.DONE_RE`, and the old fixture
    wrote `<!-- rebase-bot: <date> -->` (the shape the regex matched), which is exactly what kept
    a claim or a failure counting as a completed rebase (issue #457).
    """
    return {str(n): [{"body": f"rebased. <!-- bot-done: rebase-bot {today}T00:00:00Z rebased -->"}]
            for n in nums}


def test_the_sweep_picks_one_pr_and_states_a_reason_for_every_pass_over(tmp_path):
    gh, _log = _fake_gh(tmp_path, {"search": [], "prs": [
        _pr(1, "CLEAN", created="2026-09-01T00:00:00Z"),
        _pr(2, draft=True, created="2026-09-02T00:00:00Z"),
        _pr(3, "BEHIND", base="release/1", created="2026-09-03T00:00:00Z"),
        _pr(4, "DIRTY", created="2026-09-04T00:00:00Z"),
        _pr(5, "BEHIND", created="2026-09-05T00:00:00Z"),
    ]})
    res = rb.sweep(str(gh), f"{OWNER}/{NAME}", today="2026-10-14", own_fork="andyholst")
    assert res["action"] == "rebase" and res["pr"] == 4, res
    assert res["head_branch"] == "feat/4" and res["state"] == "DIRTY"
    joined = " | ".join(res["reasons"])
    assert "#1 is CLEAN" in joined and "#2 is a draft" in joined
    assert "#3 targets release/1" in joined


def test_a_pr_already_rebased_today_is_left_alone(tmp_path):
    """The marker comment is the record: no label needed, and no rebase loop."""
    gh, log = _fake_gh(tmp_path, {"search": [_marker_today(7)], "comments_by_pr": _marker_comments([7]),
                                  "prs": [
        _pr(7, "BEHIND", created="2026-09-01T00:00:00Z"),
        _pr(8, "BEHIND", created="2026-09-02T00:00:00Z")]})
    res = rb.sweep(str(gh), f"{OWNER}/{NAME}", today="2026-10-14", own_fork="andyholst")
    assert res["pr"] == 8, res
    assert any("already rebased today" in r for r in res["reasons"])
    q = [c for c in [json.loads(l) for l in log.read_text().splitlines()] if c[:2] == ["search", "prs"]][0]
    assert "--updated" in q and ">=2026-10-14" in q
    assert "comments" not in q[q.index("--json") + 1].split(","), q   # search has no bodies (#309)


def test_the_daily_cap_stops_the_bot(tmp_path, capsys):
    gh, log = _fake_gh(tmp_path, {"search": [_marker_today(n) for n in range(1, 6)],
                                  "comments_by_pr": _marker_comments(range(1, 6)), "prs": []})
    res = rb.sweep(str(gh), f"{OWNER}/{NAME}", today="2026-10-14")
    assert res["action"] == "cap" and res["pr"] is None
    assert "already rebased 5/5 PRs today" in res["reason"]
    assert not [c for c in [json.loads(l) for l in log.read_text().splitlines()] if c[:2] == ["pr", "list"]]


def test_a_fork_this_bot_cannot_push_to_is_skipped(tmp_path):
    gh, _log = _fake_gh(tmp_path, {"search": [], "prs": [
        _pr(9, "BEHIND", head="stranger", created="2026-09-01T00:00:00Z"),
        _pr(10, "BEHIND", head="andyholst", created="2026-09-02T00:00:00Z")]})
    res = rb.sweep(str(gh), f"{OWNER}/{NAME}", today="2026-10-14", own_fork="andyholst")
    assert res["pr"] == 10, res
    assert any("not pushable here" in r for r in res["reasons"])


def test_nothing_to_do_is_reported_as_none(tmp_path):
    gh, _log = _fake_gh(tmp_path, {"search": [], "prs": [_pr(1, "CLEAN")]})
    res = rb.sweep(str(gh), f"{OWNER}/{NAME}", today="2026-10-14", own_fork="andyholst")
    assert res["action"] == "none" and "no open PR needs rebasing" in res["reason"]


def _calls(log: Path) -> list[list[str]]:
    return [json.loads(l) for l in log.read_text().splitlines() if l.strip()]


def test_the_sweep_never_asks_search_prs_for_a_field_the_cli_lacks(tmp_path):
    """Issue #309: `gh search prs` has no comment bodies; asking for them is a hard CLI error that
    killed every run. The fake `gh` refuses it like the real CLI, so a regression fails HERE."""

    # Given a repo with a PR the sweep must consider
    gh, log = _fake_gh(tmp_path, {"search": [_marker_today(7)], "comments_by_pr": _marker_comments([7]),
                                  "prs": [_pr(7, "BEHIND", created="2026-09-01T00:00:00Z")]})

    # When the sweep runs
    res = rb.sweep(str(gh), f"{OWNER}/{NAME}", today="2026-10-14", own_fork="andyholst")

    # Then it completed (no crash) and never asked `search prs` for comment bodies
    assert res["action"] == "none", res
    searches = [c for c in _calls(log) if c[:2] == ["search", "prs"]]
    assert searches, "the search must run"
    assert all("comments" not in c[c.index("--json") + 1].split(",") for c in searches), searches


def test_a_marker_written_today_is_found(tmp_path):
    """The bot's own record for today is read from the PR's COMMENTS, not from the search row."""

    # Given search names PR 7 and its comments carry today's marker
    gh, _log = _fake_gh(tmp_path, {"search": [{"number": 7}],
                                   "comments_by_pr": _marker_comments([7], today="2026-10-14")})

    # When rebased_today runs for that day
    found = rb.rebased_today(str(gh), f"{OWNER}/{NAME}", "2026-10-14")

    # Then PR 7 is reported as already rebased
    assert found == [7], found


def test_a_marker_from_another_day_is_not_counted(tmp_path):
    """Only TODAY's marker counts; an older one must not suppress a legitimate rebase."""

    # Given PR 7's marker is for the PREVIOUS day
    gh, _log = _fake_gh(tmp_path, {"search": [{"number": 7}],
                                   "comments_by_pr": _marker_comments([7], today="2026-10-13")})

    # When rebased_today runs for 2026-10-14
    found = rb.rebased_today(str(gh), f"{OWNER}/{NAME}", "2026-10-14")

    # Then it is not counted
    assert found == [], found


def test_the_sweep_step_fails_loudly_when_the_sweep_fails():
    """Issue #309: the sweep step swallowed a crash as `action=unknown` and a green run, hiding a
    bot that never rebased anything."""

    # Given the rebase-bot workflow
    wf = yaml.safe_load((REPO / ".github/workflows/rebase-bot.yml").read_text())
    step = next(s for s in wf["jobs"]["rebase"]["steps"] if s.get("id") == "sweep")

    # When the sweep step's run block is read
    run = step["run"]

    # Then it captures the sweep's exit code and exits non-zero on a failure
    assert "make rebase-bot-sweep" in run
    assert "rc=$?" in run
    assert 'if [ "$rc" != "0" ]' in run, run
    assert "exit 1" in run, run


# ------------------------------------------------------------------------------------- actor
def _scratch_repo(tmp_path: Path):
    """A real repo with a conflicting branch and a bare `fork` remote standing in for the PR head."""
    work = tmp_path / "work"
    remote = tmp_path / "fork.git"
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com"}

    def git(*args, cwd=work):
        return subprocess.run(["git", *args], cwd=str(cwd), env=env,
                              capture_output=True, text=True, check=True)

    work.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)  # before any push
    git("init", "-q", "-b", "main")
    (work / "shared.txt").write_text("base\n")
    git("add", "-A"); git("commit", "-qm", "base")
    # the PR branch changes the same line as main will
    git("checkout", "-q", "-b", "feat/conflict")
    (work / "shared.txt").write_text("from the PR\n")
    git("add", "-A"); git("commit", "-qm", "the PR's change")
    git("push", "-q", str(remote), "feat/conflict")
    # main moves on the same line
    git("checkout", "-q", "main")
    (work / "shared.txt").write_text("from main\n")
    git("add", "-A"); git("commit", "-qm", "main moves")
    git("push", "-q", str(remote), "main")
    # both remotes point at the same bare repo: `origin` is where main lives, `fork` is the PR's
    # head repository (the actor must publish the branch THERE, not to origin)
    git("remote", "add", "origin", str(remote))
    git("remote", "add", "fork", str(remote))
    git("fetch", "-q", "origin")
    git("checkout", "-q", "main")
    return work, remote, env


def _run_actor(tmp_path, work, env, agent_cmd, dry="", gates="true"):
    return subprocess.run(
        [os.environ.get("BASH", "bash"), str(REPO / "scripts" / "rebase_bot.sh")],
        cwd=str(work), env={**env, "PR": "42", "HEAD_BRANCH": "feat/conflict",
                            "HEAD_REPO": "andyholst", "REPO": f"{OWNER}/{NAME}",
                            "AGENT_CMD": agent_cmd, "GATES": gates, "DRY": dry},
        capture_output=True, text=True, timeout=180)


def test_a_conflict_is_handed_to_the_agent_and_the_result_is_pushed_to_the_fork(tmp_path):
    """The whole point: a conflicting PR comes back onto main, resolved by the agent, published
    to the PR's own remote — with the lease, and without rerere replaying an old resolution."""
    work, remote, env = _scratch_repo(tmp_path)
    agent = tmp_path / "agent.sh"
    agent.write_text('#!/usr/bin/env bash\nset -e\ncat >/dev/null\n'
                     'printf "from main\\nfrom the PR\\n" > shared.txt\n'
                     'git add shared.txt\n')
    agent.chmod(0o755)

    r = _run_actor(tmp_path, work, env, str(agent))
    assert r.returncode == 0, r.stdout + r.stderr
    # the agent resolved it, both sides survived, and the branch was published to the fork
    assert "from main\nfrom the PR" in (work / "shared.txt").read_text()
    pushed = subprocess.run(["git", "--git-dir", str(remote), "show", "feat/conflict:shared.txt"],
                            capture_output=True, text=True, check=True).stdout
    assert "from main" in pushed and "from the PR" in pushed
    # and it never ran a merge: the branch is rebased, not merged (git's own "merge conflict"
    # message in the log is expected and is why this checks the COMMAND, not the word)
    assert "git merge" not in r.stdout.lower()
    assert "--no-ff" not in r.stdout and "merge --" not in r.stdout


def test_the_actor_uses_the_lease_never_a_plain_force(tmp_path):
    work, _remote, env = _scratch_repo(tmp_path)
    r = _run_actor(tmp_path, work, env, "true", dry="1", gates="make -n ci-unit")
    out = r.stdout
    assert "rerere.enabled=false" in out, out
    assert "--force-with-lease" in out, out
    assert "--force " not in out and "--force\n" not in out, "a plain --force must never appear"
    assert out.index("make -n ci-unit") < out.index("--force-with-lease"), "gates before the push"


def test_a_failing_agent_stops_the_run_without_pushing(tmp_path):
    work, remote, env = _scratch_repo(tmp_path)
    before = subprocess.run(["git", "--git-dir", str(remote), "rev-parse", "feat/conflict"],
                            capture_output=True, text=True, check=True).stdout.strip()
    r = _run_actor(tmp_path, work, env, "false")
    assert r.returncode != 0
    after = subprocess.run(["git", "--git-dir", str(remote), "rev-parse", "feat/conflict"],
                           capture_output=True, text=True, check=True).stdout.strip()
    assert before == after, "a failed resolution must not publish anything"


def test_it_does_not_rebase_while_the_pr_has_checks_in_flight(tmp_path):
    """A rebase would cancel the very run that is deciding the PR (and can race the fix-bot)."""
    gh, _log = _fake_gh(tmp_path, {"search": [], "checks_by_pr": {"1": ["PENDING"]},
                                   "prs": [_pr(1, "BEHIND", created="2026-09-01T00:00:00Z"),
                                           _pr(2, "BEHIND", created="2026-09-02T00:00:00Z")]})
    res = rb.sweep(str(gh), f"{OWNER}/{NAME}", today="2026-10-14", own_fork="andyholst")
    assert res["pr"] == 2, res
    assert any("checks in flight" in r for r in res["reasons"])


def _stamp(minutes_ago: int) -> str:
    ts = dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=minutes_ago)
    return ts.strftime("%Y-%m-%dT%H:%M:%SZ")


def _claim(bot="fixer", when=None, work="repair"):
    when = when or _stamp(5)
    body = "<!-- bot-claim: " + bot + " " + when + " " + work + " -->\n`" + bot + "` is " + work + "ing this now."
    return {"body": body, "createdAt": when, "author": {"login": "github-actions[bot]"}}

def _done(bot="fixer", when=None, what="repaired"):
    when = when or _stamp(1)
    return {"body": "<!-- bot-done: " + bot + " " + when + " " + what + " -->", "createdAt": when,
            "author": {"login": "github-actions[bot]"}}


def test_a_pr_the_other_bot_has_claimed_is_left_alone(tmp_path):
    """Issue #285: a fix-bot repair posts a claim; while it is fresh this bot must stand down, or
    the two of them rewrite the same branch."""
    gh, _log = _fake_gh(tmp_path, {"prs": [_pr(7, head=OWNER, created="2026-09-07T00:00:00Z")],
                                   "comments_by_pr": {"7": [_claim()]}})
    res = rb.sweep(str(gh), f"{OWNER}/{NAME}", today="2026-10-14", own_fork="andyholst")
    assert res["action"] == "none", res
    assert any("held by another bot" in r for r in res["reasons"]), res["reasons"]


def test_a_released_claim_does_not_hold_the_pr(tmp_path):
    """A `done` marker releases it - green or exhausted, the repair has ended."""
    gh, _log = _fake_gh(tmp_path, {"prs": [_pr(7, "DIRTY", head=OWNER, created="2026-09-07T00:00:00Z")],
                                   "comments_by_pr": {"7": [_claim(), _done()]}})
    res = rb.sweep(str(gh), f"{OWNER}/{NAME}", today="2026-10-14", own_fork="andyholst")
    assert res["action"] == "rebase" and res["pr"] == 7, res


def test_a_stale_claim_does_not_hold_the_pr(tmp_path):
    """A crashed repair must not freeze a PR: past PR_CLAIM_TTL the claim locks nothing."""
    stale = _claim(when=_stamp(5 * 60))          # 5 hours old
    gh, _log = _fake_gh(tmp_path, {"prs": [_pr(7, "DIRTY", head=OWNER, created="2026-09-07T00:00:00Z")],
                                   "comments_by_pr": {"7": [stale]}})
    res = rb.sweep(str(gh), f"{OWNER}/{NAME}", today="2026-10-14", own_fork="andyholst")
    assert res["action"] == "rebase" and res["pr"] == 7, res


def test_the_decision_step_claims_the_pr_IT_picked(tmp_path):
    """Issue #279: this bot force-pushes the PR's branch, and the fix-bot writes to it too - so the
    claim has to be posted by the step that DECIDES, before the actor touches anything."""
    gh, log = _fake_gh(tmp_path, {"prs": [_pr(7, "DIRTY", head=OWNER, created="2026-09-07T00:00:00Z")]})
    rb.main(["--gh", str(gh), "--repo", f"{OWNER}/llgenie", "--today", "2026-10-14"])
    calls = log.read_text().splitlines()
    claim = [c for c in calls if '"pr", "comment"' in c and "bot-claim" in c]
    assert len(claim) == 1, calls
    assert '"7"' in claim[0] and "rebase-bot" in claim[0], claim[0]


def test_the_decision_step_claims_nothing_when_nothing_is_picked(tmp_path):
    gh, log = _fake_gh(tmp_path, {"prs": [_pr(1, "CLEAN", head=OWNER)]})
    rb.main(["--gh", str(gh), "--repo", f"{OWNER}/llgenie", "--today", "2026-10-14"])
    assert not [c for c in log.read_text().splitlines() if '"pr", "comment"' in c], log.read_text()


def test_a_red_pr_that_is_only_behind_is_left_to_the_fix_bot(tmp_path):
    """Division of labour: a rebase fixes staleness, not a failing test."""
    gh, _log = _fake_gh(tmp_path, {"search": [], "checks_by_pr": {"1": ["FAILURE"], "2": ["FAILURE"]},
                                   "prs": [_pr(1, "BEHIND", created="2026-09-01T00:00:00Z"),
                                           _pr(2, "DIRTY", created="2026-09-02T00:00:00Z")]})
    res = rb.sweep(str(gh), f"{OWNER}/{NAME}", today="2026-10-14", own_fork="andyholst")
    # the conflicted one is taken even though it is red: the rebase is the precondition
    assert res["pr"] == 2, res
    assert any("the fix-bot owns that" in r for r in res["reasons"])


# --------------------------------------------------- an UNKNOWN merge state (issue #453)


def test_an_unknown_state_is_re_resolved_and_the_pr_is_taken(tmp_path):
    """GitHub's lazy mergeability must be re-asked, not read as "needs nothing"."""

    # Given an open PR the list reports as UNKNOWN, whose own read resolves to DIRTY
    gh, log = _fake_gh(tmp_path, {"search": [], "prs": [_pr(9, "UNKNOWN")],
                                  "states_by_pr": {"9": ["UNKNOWN", "DIRTY"]}})

    # When the sweep runs
    res = rb.sweep(str(gh), f"{OWNER}/{NAME}", today="2026-10-14", own_fork="andyholst",
                   unknown_delay=0)

    # Then it re-asked that PR and took it with the resolved state
    assert res["action"] == "rebase" and res["pr"] == 9, res
    assert res["state"] == "DIRTY"
    assert res["deferred"] == []
    asked = [json.loads(line) for line in log.read_text().splitlines()]
    assert any(a[:2] == ["pr", "view"] and "--json" in a for a in asked), asked


def test_a_pr_that_stays_unknown_is_deferred_not_ignored(tmp_path):
    """A PR that never resolves is named as deferred — never filed as "no rebase needed"."""

    # Given an open PR whose own read keeps reporting UNKNOWN
    gh, _log = _fake_gh(tmp_path, {"search": [], "prs": [_pr(9, "UNKNOWN")]})

    # When the sweep runs with a bounded number of re-queries
    res = rb.sweep(str(gh), f"{OWNER}/{NAME}", today="2026-10-14", own_fork="andyholst",
                   unknown_attempts=2, unknown_delay=0)

    # Then nothing is picked, and the PR is reported as deferred with the next-run retry
    assert res["action"] == "none", res
    assert res["deferred"] == [9]
    joined = " | ".join(res["reasons"])
    assert "#9 has no computed merge state (UNKNOWN)" in joined
    assert "deferred to the next run" in joined


def test_the_rebase_step_exports_gh_token(tmp_path):
    """The step that posts the outcome comment (and its done marker) carries GH_TOKEN."""

    # Given the rebase bot's workflow file
    wf = yaml.safe_load((REPO / ".github" / "workflows" / "rebase-bot.yml").read_text())
    steps = wf["jobs"]["rebase"]["steps"]

    # When the step that runs the actor is found
    actor = next(s for s in steps if str(s.get("name", "")).startswith("Rebase it"))

    # Then it exports the job token, so `gh pr comment` can post the done marker
    assert actor["env"]["GH_TOKEN"] == "${{ github.token }}"
    assert "make rebase-bot" in actor["run"]


def test_the_cli_passes_the_unknown_state_bounds(tmp_path, capsys):
    """The dispatcher can tighten the re-query bound (the workflow keeps the default)."""

    # Given a PR that stays UNKNOWN and an explicit bound on the command line
    gh, _log = _fake_gh(tmp_path, {"search": [], "prs": [_pr(9, "UNKNOWN")]})

    # When the CLI runs with one attempt and no delay
    rc = rb.main(["--gh", str(gh), "--repo", f"{OWNER}/{NAME}", "--today", "2026-10-14",
                  "--own-fork", "andyholst", "--unknown-attempts", "1", "--unknown-delay", "0"])

    # Then it exits 0, reports the deferral, and files no rebase
    out = capsys.readouterr().out
    assert rc == 0
    assert "action=none" in out
    assert "deferred to the next run" in out


# ------------------------------------ "already rebased today" reads the DONE marker (issue #457)


def _claim_body(today="2026-10-14"):
    """The claim the sweep itself posts before a rebase starts."""
    return (f"<!-- bot-claim: rebase-bot {today}T06:22:00Z rebase ttl=30m run=123 -->\n"
            "`rebase-bot` is rebaseing this now. Other bots: leave it alone for the next 30 minutes.")


def _done_body(kind, today="2026-10-14"):
    return f"an outcome. <!-- bot-done: rebase-bot {today}T06:30:00Z {kind} -->"


def test_a_claim_is_not_a_rebase_record(tmp_path):
    """The bot's own claim must not count as a completed rebase for the day."""

    # Given a DIRTY PR whose only bot comment is the claim it posted before starting
    gh, _log = _fake_gh(tmp_path, {"search": [_marker_today(9)],
                                   "comments_by_pr": {"9": [{"body": _claim_body()}]},
                                   "prs": [_pr(9, "DIRTY")]})

    # When the sweep runs
    res = rb.sweep(str(gh), f"{OWNER}/{NAME}", today="2026-10-14", own_fork="andyholst",
                   unknown_delay=0)

    # Then the claim is not the record, and the PR is picked again
    assert res["action"] == "rebase" and res["pr"] == 9, res
    assert "already rebased today" not in " | ".join(res["reasons"])


def test_a_rebased_done_marker_is_the_record(tmp_path):
    """A `rebased` DONE marker dated today keeps the PR out of the day's work."""

    # Given a PR whose thread carries today's `rebased` marker
    gh, _log = _fake_gh(tmp_path, {"search": [_marker_today(7)],
                                   "comments_by_pr": {"7": [{"body": _done_body("rebased")}]},
                                   "prs": [_pr(7, "BEHIND")]})

    # When the sweep runs
    res = rb.sweep(str(gh), f"{OWNER}/{NAME}", today="2026-10-14", own_fork="andyholst",
                   unknown_delay=0)

    # Then it is passed over as already rebased
    assert res["action"] == "none", res
    assert "#7 was already rebased today" in " | ".join(res["reasons"])


def test_a_gave_up_marker_does_not_record_the_day(tmp_path):
    """A failed attempt records `gave-up`, so the PR stays eligible for a retry today."""

    # Given a PR whose thread carries today's `gave-up` marker
    gh, _log = _fake_gh(tmp_path, {"search": [_marker_today(9)],
                                   "comments_by_pr": {"9": [{"body": _done_body("gave-up")}]},
                                   "prs": [_pr(9, "DIRTY")]})

    # When the sweep runs
    res = rb.sweep(str(gh), f"{OWNER}/{NAME}", today="2026-10-14", own_fork="andyholst",
                   unknown_delay=0)

    # Then the failure is not the record, and the PR is picked
    assert res["action"] == "rebase" and res["pr"] == 9, res


def test_the_actor_records_rebased_only_on_success():
    """The script writes kind `rebased` on the push path and `gave-up` on every failure path."""

    # Given the rebase actor's shell script
    script = (REPO / "scripts" / "rebase_bot.sh").read_text()

    # When its comment helper and its outcome lines are read
    # Then the helper defaults to gave-up, and the success call passes rebased explicitly
    assert 'local kind="${2:-gave-up}"' in script
    success = [l for l in script.splitlines() if l.startswith('comment "$OUTCOME')]
    assert success and success[0].rstrip().endswith(" rebased")

    # And no failure path claims to have rebased
    failures = [l for l in script.splitlines()
                if l.lstrip().startswith("comment \"The rebase bot")]
    assert failures, "the failure paths should comment"
    assert not any(l.rstrip().endswith(" rebased") for l in failures)
