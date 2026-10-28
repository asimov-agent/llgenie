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
from scripts import rebase_bot_sweep as rb

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
    #: PRs whose `pr checks` answers the documented non-zero: "no checks reported" (issue #801).
    (tmp_path / "nochecks.json").write_text(json.dumps(opts.get("no_checks_by_pr", [])))
    #: PRs whose `pr view --json comments` read fails hard (a real crash, not a no-checks answer).
    (tmp_path / "failcomments.json").write_text(json.dumps(opts.get("fail_comments_by_pr", [])))
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
        broke = here / "failcomments.json"
        if broke.exists() and args[2] in [str(x) for x in json.loads(broke.read_text())]:
            sys.stderr.write('GraphQL: Resource not accessible (addComment)\\n')
            sys.exit(1)                  # a REAL read failure: still a hard error, never "no checks"
        f = here / "comments.json"
        by_pr = json.loads(f.read_text()) if f.exists() else {{}}
        print(json.dumps({{"comments": by_pr.get(args[2], [])}}))
elif args[:2] == ["pr", "checks"]:
    none = here / "nochecks.json"
    if none.exists() and args[2] in [str(x) for x in json.loads(none.read_text())]:
        # EXACTLY what the real `gh` does for a PR with no CI run (a DIRTY PR, issue #801).
        sys.stderr.write("no checks reported on the 'feat/%s' branch\\n" % args[2])
        sys.exit(1)
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


def test_a_pr_rebased_today_but_clean_is_left_alone(tmp_path):
    """Today's marker bounds the daily cap; a CLEAN PR needs nothing either way."""
    gh, log = _fake_gh(tmp_path, {"search": [_marker_today(7)], "comments_by_pr": _marker_comments([7]),
                                  "prs": [
        _pr(7, "CLEAN", created="2026-09-01T00:00:00Z"),
        _pr(8, "BEHIND", created="2026-09-02T00:00:00Z")]})
    res = rb.sweep(str(gh), f"{OWNER}/{NAME}", today="2026-10-14", own_fork="andyholst")
    assert res["pr"] == 8, res
    assert any("#7 is CLEAN" in r for r in res["reasons"])
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
                                  "prs": [_pr(7, "CLEAN", created="2026-09-01T00:00:00Z")]})

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
    step = next(s for s in wf["jobs"]["rebase"]["steps"] if s.get("id") == "drain")

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

    # And the tree is left with NO stopped rebase: the next `make` in the same run has to parse
    # Makefile, which is exactly the file a failed conflict can leave broken (issues #460/#462).
    mid_rebase = subprocess.run(["git", "-C", str(work), "rev-parse", "-q", "--verify", "REBASE_HEAD"],
                                capture_output=True, text=True)
    assert mid_rebase.returncode != 0, "a failed rebase was left half-done for the next step"
    assert not (work / ".git" / "rebase-merge").exists()
    assert not (work / ".git" / "rebase-apply").exists()


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


def _claim(bot="fix-bot", when=None, work="fix"):
    when = when or _stamp(5)
    body = "<!-- bot-claim: " + bot + " " + when + " " + work + " -->\n`" + bot + "` is " + work + "ing this now."
    return {"body": body, "createdAt": when, "author": {"login": "github-actions[bot]"}}

def _done(bot="fixer", when=None, what="repaired"):
    when = when or _stamp(1)
    return {"body": "<!-- bot-done: " + bot + " " + when + " " + what + " -->", "createdAt": when,
            "author": {"login": "github-actions[bot]"}}


def test_a_plain_comment_does_not_hold_a_pr_that_is_behind(tmp_path):
    """A status note is not a claim. A PR behind main is rebased anyway."""

    # Given a PR that is BEHIND, carrying a person's recent note and no claim marker
    note = {"body": "Local gate: make test-unit passed.", "createdAt": _stamp(90),
            "author": {"login": "andyholst"}}
    gh, _log = _fake_gh(tmp_path, {"prs": [_pr(498, "BEHIND", head="andyholst",
                                               created="2026-09-07T00:00:00Z")],
                                   "comments_by_pr": {"498": [note]}})

    # When  the sweep runs
    res = rb.sweep(str(gh), f"{OWNER}/{NAME}", today="2026-10-14", own_fork="andyholst")

    # Then  the note does not hold it, and it is selected for rebase
    assert res["action"] == "rebase" and res["pr"] == 498, res
    assert not any("held by another bot" in r for r in res["reasons"]), res["reasons"]


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
    actor = next(s for s in steps if str(s.get("name", "")).startswith("Rebase every eligible PR"))

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


def test_a_rebased_done_marker_is_the_days_record(tmp_path):
    """A `rebased` DONE marker dated today is the daily-cap record (not a bar to a needed rebase)."""

    # Given a PR whose thread carries today's `rebased` marker, and it is behind again
    gh, _log = _fake_gh(tmp_path, {"search": [_marker_today(7)],
                                   "comments_by_pr": {"7": [{"body": _done_body("rebased")}]},
                                   "prs": [_pr(7, "BEHIND")]})

    # When the record is read and the sweep runs
    done = rb.rebased_today(str(gh), f"{OWNER}/{NAME}", "2026-10-14")
    res = rb.sweep(str(gh), f"{OWNER}/{NAME}", today="2026-10-14", own_fork="andyholst",
                   unknown_delay=0)

    # Then the marker counts for the cap, and the re-dirtied PR is still picked
    assert done == [7]
    assert res["action"] == "rebase" and res["pr"] == 7, res


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


# --------------------------- the conflict agent is reachable mid-rebase (issue #460)


def test_the_agent_is_invoked_through_a_pre_checkout_makefile_snapshot():
    """A conflicted Makefile must not stop `make` from reaching the agent."""

    # Given the rebase actor's shell script
    script = (REPO / "scripts" / "rebase_bot.sh").read_text()

    # When the snapshot and the command that uses it are located
    snap = script.index('MK_SNAPSHOT="$(mktemp)"')
    copy = script.index('cp Makefile "$MK_SNAPSHOT"')
    checkout = script.index('run git checkout -B "$HEAD_BRANCH"')

    # Then the Makefile is snapshotted BEFORE the conflicted checkout …
    assert snap < checkout and copy < checkout, "the snapshot must precede the checkout"

    # … and the agent leg is reached through it, so `make` has a file that parses
    assert 'AGENT_CMD="${AGENT_CMD:-make -f $MK_SNAPSHOT rebase-bot-agent}"' in script


def test_the_agent_recipe_runs_hermes_directly_inside_the_image():
    """The container must not re-read the conflicted Makefile to launch the agent."""

    # Given the Makefile's rebase agent leg
    mk = (REPO / "Makefile").read_text()
    recipe = mk.split("rebase-bot-agent:", 1)[1].split("\nrebase-bot:", 1)[0]

    # Then it runs Hermes inline, inside the redacting public leg, with the model pin's one alias
    assert "hermes -z" in recipe
    assert "$(nous-alias)" in recipe
    assert "$(call scrubbed_run," in recipe

    # And no nested make target exists (it would parse the conflicted file)
    assert "bash -lc 'make _rebase-bot-agent'" not in recipe
    assert "\n_rebase-bot-agent:" not in mk


# ------------------------------- one run drains the backlog (issue #462)


def _drain_step() -> dict:
    wf = yaml.safe_load((REPO / ".github" / "workflows" / "rebase-bot.yml").read_text())
    return next(s for s in wf["jobs"]["rebase"]["steps"]
                if str(s.get("name", "")).startswith("Rebase every eligible PR"))


def test_the_run_drains_every_eligible_pr_up_to_the_bound():
    """The run re-asks the sweep after each rebase instead of stopping after one PR."""

    # Given the rebase workflow's drain step
    script = _drain_step()["run"]
    wf = yaml.safe_load((REPO / ".github" / "workflows" / "rebase-bot.yml").read_text())
    on = wf.get("on") or wf.get(True)

    # When the loop, its bound and its stop condition are read
    # Then it loops up to MAX_PR, asking the sweep each time
    assert 'for i in $(seq 1 "$MAX_PR")' in script
    assert 'MAX_PR="${MAX_PR:-10}"' in script, "the step must bound itself when run alone"
    assert 'make rebase-bot-sweep REPO="$REPO" OWN_FORK=andyholst' in script
    assert 'make rebase-bot REPO="$REPO" PR="$pr" HEAD_BRANCH="$branch" HEAD_REPO="$headrepo"' in script

    # And it stops as soon as the sweep no longer says rebase
    assert 'if [ "$action" != "rebase" ]' in script and "break" in script

    # And `max_prs` is a documented dispatch input with a default
    spec = on["workflow_dispatch"]["inputs"]["max_prs"]
    assert len(spec["description"]) >= 10 and "default" in spec


def test_a_failed_rebase_is_aborted_and_reported_without_stopping_the_loop():
    """One bad PR is aborted, counted, and the rest are still processed; the run ends red."""

    # Given the drain step
    script = _drain_step()["run"]

    # When a `make rebase-bot` invocation fails
    # Then the tree is reset for the next decision, the failure counted, and the loop continues
    assert "make rebase-bot-abort" in script
    assert "failed=$((failed + 1))" in script
    assert "::warning title=Rebase failed::" in script

    # And the step exits non-zero at the end, naming the failures
    assert 'if [ "$failed" != "0" ]' in script
    assert script.rstrip().endswith("fi")


def test_the_abort_target_resets_the_tree_to_main():
    """`make rebase-bot-abort` is a documented, phony target that leaves the tree on main."""

    # Given the Makefile, README and .PHONY block
    mk = (REPO / "Makefile").read_text()
    readme = (REPO / "README.md").read_text()
    phony = mk.split(".PHONY:", 1)[1].split("\n\n", 1)[0]

    # When the abort target is read
    body = mk.split("rebase-bot-abort:", 1)[1].split("\nrebase-bot:", 1)[0]

    # Then it aborts a stopped rebase and returns to main, and it is wired like every other target
    assert "git rebase --abort" in body
    assert "git checkout -q main" in body
    assert "rebase-bot-abort" in phony
    assert "rebase-bot-abort" in readme


# ------------------- a rebase this morning must not block a rebase this afternoon (issue #467)


def test_a_pr_rebased_today_that_main_re_dirtied_is_picked_again(tmp_path):
    """The marker bounds the daily cap, not eligibility: main moving re-dirties the PR."""

    # Given a PR carried today's `rebased` marker and it is CONFLICTING again
    gh, _log = _fake_gh(tmp_path, {"search": [_marker_today(7)],
                                   "comments_by_pr": _marker_comments([7]),
                                   "prs": [_pr(7, "DIRTY", created="2026-09-01T00:00:00Z")]})

    # When the sweep runs later the same day
    res = rb.sweep(str(gh), f"{OWNER}/{NAME}", today="2026-10-14", own_fork="andyholst",
                   unknown_delay=0)

    # Then the PR is picked again instead of waiting for the date to roll over
    assert res["action"] == "rebase" and res["pr"] == 7, res
    assert not any("already rebased today" in r for r in res["reasons"])


def test_the_run_skips_the_prs_it_already_rebased_in_this_run(tmp_path):
    """One run must not pick the same PR twice — that is what `--skip` is for."""

    # Given two DIRTY PRs, one of which this run already rebased
    gh, _log = _fake_gh(tmp_path, {"search": [], "prs": [
        _pr(7, "DIRTY", created="2026-09-01T00:00:00Z"),
        _pr(8, "DIRTY", created="2026-09-02T00:00:00Z")]})

    # When the sweep is told to skip #7
    res = rb.sweep(str(gh), f"{OWNER}/{NAME}", today="2026-10-14", own_fork="andyholst",
                   unknown_delay=0, skip=[7])

    # Then it picks the other one, and says why
    assert res["action"] == "rebase" and res["pr"] == 8, res
    assert any("#7 was already rebased in this run" in r for r in res["reasons"])


def test_the_loop_passes_the_prs_it_already_did():
    """The workflow's loop tells the sweep which PRs it handled, so no PR repeats in one run."""

    # Given the drain step's script
    script = _drain_step()["run"]

    # Then it starts empty, passes SKIP to the sweep, and appends every PR it handled — the
    # successful ones AND the failed ones (a failure is still DIRTY, so re-picking it in the same
    # loop would spend another model call on the same conflict).
    assert 'skip=""' in script
    assert 'SKIP="$skip"' in script
    assert script.count('skip="${skip:+$skip,}$pr"') == 2, script


# ------------------------------ the structural gate really gates the push (issue #455)


def test_the_structural_gate_fails_closed(tmp_path):
    """A failing gate must block the push — the `;` list used to swallow it."""
    work, remote, env = _scratch_repo(tmp_path)
    before = subprocess.run(["git", "--git-dir", str(remote), "rev-parse", "feat/conflict"],
                            capture_output=True, text=True, check=True).stdout.strip()

    # Given a rebase that applies cleanly but a structural gate that fails
    r = _run_actor(tmp_path, work, env, "true", gates="false")

    # Then the run stops, and nothing is published
    assert r.returncode != 0, r.stdout + r.stderr
    after = subprocess.run(["git", "--git-dir", str(remote), "rev-parse", "feat/conflict"],
                           capture_output=True, text=True, check=True).stdout.strip()
    assert before == after, "a failing gate must not publish the branch"


def test_the_default_gate_chain_and_the_pull_it_needs():
    """The default gates are chained with &&, and the workflow pulls the image lint runs in."""
    script = (REPO / "scripts" / "rebase_bot.sh").read_text()
    wf = (REPO / ".github" / "workflows" / "rebase-bot.yml").read_text()

    # Then every gate is required, not just the last one
    line = next(l for l in script.splitlines() if l.startswith('GATES="${GATES:-'))
    assert "make -n ci-unit && make lint && make check-wiring" in line, line

    # And the runner pulls the test image before the drain step needs it
    assert "make test-image" in wf
    assert wf.index("make test-image") < wf.index("Rebase every eligible PR")


def test_a_conflicted_pr_with_no_checks_is_a_decision_not_a_crash(tmp_path):
    """Run 40700214889's failure: `gh pr checks` exits 1 "no checks reported" on the DIRTY PR.

    A conflicted PR gets no CI run at all (GitHub builds no merge ref), so "no checks reported" is
    the NORMAL answer for exactly the PR this bot exists to rebase. Reading that exit code as a
    crash killed the sweep on its own target and left the PR with no checks forever (issue #801).
    """

    # Given a conflicted (DIRTY) PR with no checks at all, which makes `gh pr checks` exit 1
    gh, _log = _fake_gh(tmp_path, {"search": [], "prs": [_pr(789, "DIRTY", head=OWNER)],
                                   "no_checks_by_pr": ["789"]})

    # When  the sweep judges the open PRs
    res = rb.sweep(str(gh), f"{OWNER}/{NAME}", today="2026-10-14", own_fork="andyholst")

    # Then  it answers with the rebase decision instead of dying on the checks read
    assert res["action"] == "rebase", res
    assert res["pr"] == 789


def test_a_real_read_failure_names_the_pr_it_prevented(tmp_path, capsys):
    """A crash must name the PR: a bare exit code hid the one PR that needed the rebase (#801)."""

    # Given a PR whose comments read fails for a reason that is NOT "no checks reported"
    gh, _log = _fake_gh(tmp_path, {"search": [], "prs": [_pr(812, "DIRTY", head=OWNER)],
                                   "fail_comments_by_pr": ["812"]})

    # When  the sweep judges the open PRs
    res = rb.sweep(str(gh), f"{OWNER}/{NAME}", today="2026-10-14", own_fork="andyholst")

    # Then  the decision is an error that names the PR, and no rebase is claimed from a partial scan
    assert res["action"] == "error", res
    assert any("#812" in c for c in res["crashed"]), res
    assert "#812" in capsys.readouterr().out


def test_the_cli_reports_the_named_failure_on_stdout_and_exits_non_zero(tmp_path, capsys):
    """`make rebase-bot-sweep` must print what it could not read before the workflow goes red."""

    # Given the same unreadable PR, driven through the CLI the workflow actually calls
    gh, _log = _fake_gh(tmp_path, {"search": [], "prs": [_pr(812, "DIRTY", head=OWNER)],
                                   "fail_comments_by_pr": ["812"]})

    # When  the CLI runs
    rc = rb.main(["--gh", str(gh), "--repo", f"{OWNER}/{NAME}", "--today", "2026-10-14",
                  "--own-fork", "andyholst"])
    out = capsys.readouterr().out

    # Then  it prints the decision and the named failure, and exits non-zero
    assert rc == 1
    assert "action=error" in out, out
    assert "error=#812" in out, out


# ---- the four outcomes of one PR's merge state (issue #801) --------------------------------
# Four, never three: `UNKNOWN` is its own answer (#453) and a crashed read is its own answer (#801).
# The negative control in each case is the outcome it must NOT be — that is the assertion a future
# refactor breaks first, and it is why each case asserts a pair rather than a single value.


def test_a_conflicted_pr_is_a_rebase():
    assert rb.outcome("DIRTY") is rb.REBASE
    assert rb.outcome("BEHIND") is rb.REBASE
    assert rb.outcome("dirty") is rb.REBASE, "the state is case-insensitive"


def test_a_clean_pr_is_none_not_defer():
    assert rb.outcome("MERGEABLE") is rb.NONE
    assert rb.outcome("BLOCKED") is rb.NONE, "a required check pending is not a rebase"
    assert rb.outcome("CLEAN") is rb.NONE
    assert rb.outcome("MERGEABLE") is not rb.DEFER


def test_an_uncomputed_state_is_defer_and_never_none():
    assert rb.outcome("UNKNOWN") is rb.DEFER
    assert rb.outcome("") is rb.NONE, "an absent field is not UNKNOWN — gh omitted it"
    assert rb.outcome("UNKNOWN") is not rb.NONE, "collapsing this is what left #445-#447 stale"


def test_a_crashed_read_is_error_even_with_a_rebasable_state():
    assert rb.outcome("DIRTY", crashed=True) is rb.ERROR
    assert rb.outcome("UNKNOWN", crashed=True) is rb.ERROR
    assert rb.outcome("DIRTY", crashed=True) is not rb.REBASE, (
        "a crashed read must never be read as 'this PR needs a rebase' — the sweep did not see it")


def test_the_four_outcomes_are_distinct_values():
    """The structural control: a refactor that collapses two outcomes cannot keep these four names."""
    values = {rb.REBASE, rb.NONE, rb.DEFER, rb.ERROR}
    assert len(values) == 4, values


# ---- item 4: a crashed sweep surfaces on the PR it prevented (issue #801) -------------------


def test_a_crashed_sweep_comments_on_the_pr_it_could_not_read():
    """A DIRTY PR has no CI run and `fix-bot` only watches failing checks, so a red run alone is invisible."""
    posted = []

    def fake_post(gh, args):
        posted.append(args)
        return "https://example.invalid/comment"

    surfaced = rb.surface_crashes(
        "gh", "o/r", ["#789 (agent/issue-772-a-scaffolded) could not be read: gh pr view failed"], fake_post)

    assert surfaced == [789]
    assert len(posted) == 1
    assert posted[0][:4] == ["pr", "comment", "789", "--repo"]
    body = posted[0][posted[0].index("--body") + 1]
    assert "could not decide this PR" in body
    assert "#789 (agent/issue-772-a-scaffolded) could not be read" in body, "the cause is quoted verbatim"
    assert "#801" in body


def test_one_comment_per_pr_even_when_several_reads_of_it_crashed():
    posted = []
    surfaced = rb.surface_crashes(
        "gh", "o/r",
        ["#42 (b) could not be read: boom", "#42 (b) could not be read: boom again", "#43 (c) could not be read: x"],
        lambda gh, args: posted.append(args))
    assert surfaced == [42, 43], "no duplicate comments on the same PR"
    assert len(posted) == 2


def test_a_crash_line_without_a_pr_number_posts_nothing():
    """The control: a failure that names no PR must not invent one, and must not go silent either."""
    posted = []
    assert rb.surface_crashes("gh", "o/r", ["the PR list could not be read"], lambda gh, args: posted.append(args)) == []
    assert posted == []
