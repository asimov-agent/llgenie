"""Which ONE open PR the rebase bot should bring back onto `main` (issue #246).

The bot runs every 6 hours (`.github/workflows/rebase-bot.yml`). AGENTS.md and issue #107 forbid
a CI job that can skip itself, so the workflow is ONE job that always runs and this decides:
*one PR per run*, with a stated reason for every PR it passes over.

What it looks for: an open, non-draft PR against `main` whose merge state is BEHIND (a clean
rebase) or DIRTY (conflicts the agent has to resolve).

It also keeps out of the other bots' way, because three of them touch branches:

  * a PR with checks IN FLIGHT is skipped — rebasing it would cancel the run that is deciding it;
  * a merely-BEHIND PR that is RED is the FIX-BOT's, not this one's (a rebase fixes staleness, not a
    failing test); a CONFLICTED PR is taken even when red, because the rebase is the precondition
    for everything else;
  * the implementer never has a PR here to race — it pushes a NEW branch and only then opens the PR,
    which is therefore fresh, and the refiner never touches a branch at all.
 A PR this bot already rebased **today** is
left alone — the marker comment it posts is the record — so a PR cannot be rebased in a loop, and
the daily cap bounds the work.

The push target follows the PR's HEAD repository, never `origin` blindly: pushing a fork PR's
branch to `origin` is the mistake that leaves a stray branch on the wrong remote.

Read-only: this chooses and prints. `scripts/rebase_bot.sh` does the work.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import datetime as dt
from datetime import datetime, timezone

import bot_claims

#: Marks this bot's own comments, so its records are found without inventing a label.
MARKER = "rebase-bot"
#: PRs one bot may rebase in a UTC day (each 6-hourly run handles one).
#: How long this bot's own claim holds. A rebase is minutes, and its actor releases the claim from
#: the comment it posts, so this is only the floor for a run that dies without a word - short on
#: purpose: the readers age a claim by their own TTL and a crash must not freeze a PR for hours.
REBASE_CLAIM_TTL = dt.timedelta(minutes=30)

MAX_PER_DAY = 5
#: Merge states that mean "this branch has to come back onto main".
NEEDS = ("BEHIND", "DIRTY")


def _gh(gh: str, args: list[str]) -> str:
    r = subprocess.run([gh, *args], capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"[rebase-bot] {gh} {' '.join(args)} failed ({r.returncode}): {r.stderr.strip()}")
    return r.stdout




#: Cache of the liveness probe: one lookup per run id per process (scripts/bot_claims.py, #291).
_LIVE: dict[int, "bool | None"] = {}


def run_is_live(gh: str, run_id: int) -> "bool | None":
    """Whether the run that posted a claim is still going (cached).

    A cancelled/preempted run must not hold a subject for the rest of the claim's TTL (#291): the
    marker carries the run, and this asks GitHub about it. Unknown stays unknown - it never
    releases a claim.
    """
    if run_id not in _LIVE:
        _LIVE[run_id] = bot_claims.run_is_live(lambda args: _gh(gh, args), run_id)
    return _LIVE[run_id]


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def rebased_today(gh: str, repo: str, today: str) -> list[int]:
    """PR numbers carrying this bot's marker for today (its own audit trail, no label)."""
    out = _gh(gh, ["search", "prs", "--repo", repo, "--commenter", "github-actions[bot]",
                   "--updated", f">={today}", "--json", "number,comments", "--limit", "50"])
    done = []
    for pr in json.loads(out or "[]") or []:
        body = json.dumps(pr.get("comments") or [])
        if re.search(rf"{MARKER}[^0-9]{{0,40}}{re.escape(today)}", body):
            done.append(pr["number"])
    return done


def _comments(gh: str, repo: str, num: int) -> list[dict]:
    """This PR's comments — where the claim protocol lives (scripts/bot_claims.py).

    Asked for through `--json` alone: `gh` REFUSES `--comments` together with `--json`.
    """
    out = _gh(gh, ["pr", "view", str(num), "--repo", repo, "--json", "comments"])
    return (json.loads(out or "{}") or {}).get("comments") or []


def _checks(gh: str, repo: str, num: int) -> tuple[bool, bool]:
    """(is anything still running, is anything red) for this PR, from its checks.

    Both matter for coexisting with the other bots: rebasing cancels an in-flight run, and a
    failing test is the fix-bot's business rather than something a rebase can fix.
    """
    out = _gh(gh, ["pr", "checks", str(num), "--repo", repo, "--json", "state"])
    states = [(c.get("state") or "").upper() for c in (json.loads(out or "[]") or [])]
    running = any(s in ("PENDING", "IN_PROGRESS", "QUEUED", "EXPECTED", "WAITING") for s in states)
    red = any(s in ("FAILURE", "ERROR", "FAIL", "CANCELLED", "TIMED_OUT") for s in states)
    return running, red


def sweep(gh: str, repo: str, today: str | None = None, max_per_day: int = MAX_PER_DAY,
          own_fork: str | None = None) -> dict:
    """Pick the one PR to rebase, or explain why none is."""
    d = today or _today()
    done = rebased_today(gh, repo, d)
    if len(done) >= max_per_day:
        return {"action": "cap", "pr": None, "reasons": [],
                "reason": f"already rebased {len(done)}/{max_per_day} PRs today"}
    owner = repo.split("/")[0].lower()
    prs = json.loads(_gh(gh, ["pr", "list", "--repo", repo, "--state", "open", "--limit", "100",
                              "--json", "number,title,isDraft,mergeStateStatus,headRefName,"
                                        "headRepositoryOwner,createdAt,baseRefName"]) or "[]") or []
    reasons = []
    for pr in sorted(prs, key=lambda p: p.get("createdAt") or ""):
        num = pr.get("number")
        head_repo = ((pr.get("headRepositoryOwner") or {}).get("login") or "").lower()
        if pr.get("isDraft"):
            reasons.append(f"#{num} is a draft"); continue
        if (pr.get("baseRefName") or "main") != "main":
            reasons.append(f"#{num} targets {pr.get('baseRefName')}, not main"); continue
        if num in done:
            reasons.append(f"#{num} was already rebased today"); continue
        if head_repo not in (owner, (own_fork or "").lower()):
            reasons.append(f"#{num} lives on {head_repo or 'an unknown repo'} (not pushable here)")
            continue
        state = (pr.get("mergeStateStatus") or "").upper()
        if state not in NEEDS:
            reasons.append(f"#{num} is {state or 'unknown'} against main"); continue
        # --- coexistence with the other bots: never invalidate a run, never race the fix-bot ---
        # A claim is how the other bot says "I am on this branch" (issue #285): a fix-bot repair
        # spends up to 180 minutes in the agent with nothing in flight and no commit yet, so the
        # checks and the attempt counter both look idle. A claim from ANY other bot makes this PR
        # theirs; a `done` marker releases it, and a claim older than PR_CLAIM_TTL is ignored.
        comments = _comments(gh, repo, num)
        held = bot_claims.occupied(comments, bot_claims.REBASER, ttl=bot_claims.PR_CLAIM_TTL,
                                   is_live=lambda rid: run_is_live(gh, rid))
        if held:
            reasons.append(f"#{num} is held by another bot: {held}")
            continue
        gone = bot_claims.released(comments, bot_claims.REBASER, ttl=bot_claims.PR_CLAIM_TTL,
                                   is_live=lambda rid: run_is_live(gh, rid))
        if gone:
            # #291: the PR is free because its holder is gone; say so instead of waiting silently.
            print(f"[rebase-bot] #{num}: {gone}")
        running, red = _checks(gh, repo, num)
        if running:
            reasons.append(f"#{num} has checks in flight; rebasing now would cancel that run")
            continue
        if red and state == "BEHIND":
            reasons.append(f"#{num} is red and only behind: the fix-bot owns that, a rebase is not "
                           "the blocker (a conflicted PR is taken, since the rebase is one)")
            continue
        return {"action": "rebase", "pr": num, "head_branch": pr.get("headRefName"),
                "head_repo": head_repo or owner, "state": state, "title": pr.get("title"),
                "fingerprint": f"{head_repo}:{pr.get('headRefName')}",
                "reasons": reasons, "reason": f"#{num} is {state} against main"}
    return {"action": "none", "pr": None, "reasons": reasons, "reason": "no open PR needs rebasing"}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="rebase_bot_sweep")
    p.add_argument("--gh", default="gh")
    p.add_argument("--repo", required=True)
    p.add_argument("--today", default=None)
    p.add_argument("--max-per-day", type=int, default=MAX_PER_DAY)
    p.add_argument("--own-fork", default=None,
                   help="the owner whose fork this bot may push to (e.g. andyholst)")
    a = p.parse_args(argv)
    res = sweep(a.gh, a.repo, a.today, a.max_per_day, a.own_fork)
    for r in res["reasons"]:
        print(f"[rebase-bot] pass-over: {r}")
    print(f"[rebase-bot] {res['reason']}")
    if res["action"] == "rebase":
        # CLAIM it here, in the decision step, BEFORE the actor force-pushes this branch
        # (scripts/bot_claims.py, issues #279/#285). The fix-bot writes to the same branch, and
        # `sweep()` above is what made sure nobody else holds it.
        posted = _gh(a.gh, ["pr", "comment", str(res["pr"]), "--repo", a.repo, "--body",
                            bot_claims.claim_comment(bot_claims.REBASER, "rebase",
                                                     dt.datetime.now(dt.timezone.utc),
                                                     ttl=REBASE_CLAIM_TTL,
                                                     run_id=os.environ.get("GITHUB_RUN_ID"))])
        print(f"[rebase-bot] claimed #{res['pr']} for {bot_claims.REBASER} "
              f"({int(REBASE_CLAIM_TTL.total_seconds() // 60)} min){'' if posted else ' — the comment did not post'}")
    print(f"action={res['action']}")
    for k in ("pr", "head_branch", "head_repo"):
        if res.get(k):
            print(f"{k}={res[k]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
