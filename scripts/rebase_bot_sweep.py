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
import subprocess
import time
import datetime as dt
from datetime import datetime, timezone

import bot_claims

#: The `bot-done` kind that means "this PR really was rebased today". A claim, a `gave-up`, and
#: any other kind do NOT count: reading "any comment that names the bot" is what turned a failed
#: attempt into a whole day of doing nothing (issue #457).
REBASED_KIND = "rebased"
#: PRs one bot may rebase in a UTC day (each 6-hourly run handles one).
#: How long this bot's own claim holds. A rebase is minutes, and its actor releases the claim from
#: the comment it posts, so this is only the floor for a run that dies without a word - short on
#: purpose: the readers age a claim by their own TTL and a crash must not freeze a PR for hours.
REBASE_CLAIM_TTL = dt.timedelta(minutes=30)

MAX_PER_DAY = 5
#: Merge states that mean "this branch has to come back onto main".
NEEDS = ("BEHIND", "DIRTY")
#: GitHub computes mergeability lazily: a `pr list` right after a push/comment can report
#: `UNKNOWN` for every PR. Treating that as "no rebase needed" is what left #445-#447 stale
#: (issue #453), so a PR reported UNKNOWN is re-queried — bounded, never an unbounded poll.
UNKNOWN_ATTEMPTS = 4
UNKNOWN_DELAY_S = 3.0


def _gh(gh: str, args: list[str]) -> str:
    r = subprocess.run([gh, *args], capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"[rebase-bot] {gh} {' '.join(args)} failed ({r.returncode}): {r.stderr.strip()}")
    return r.stdout


def resolve_state(gh: str, repo: str, num: int, state: str,
                  attempts: int = UNKNOWN_ATTEMPTS, delay: float = UNKNOWN_DELAY_S) -> str:
    """The PR's merge state, re-asked while GitHub has not computed it yet (issue #453).

    `UNKNOWN` is not an answer: it means the mergeability computation has not finished, and it is
    what a fresh `pr list` returns right after a push or a comment. The single-PR read
    (`gh pr view`) is the cheap way to get the computed value, and a few re-queries turn a
    transient UNKNOWN into the real BEHIND/DIRTY. A state that never resolves is returned as
    UNKNOWN so the caller can DEFER the PR by name instead of pretending it needs nothing.
    """
    if state and state != "UNKNOWN":
        return state
    for attempt in range(1, attempts + 1):
        time.sleep(delay)
        out = _gh(gh, ["pr", "view", str(num), "--repo", repo, "--json", "mergeStateStatus"])
        state = (json.loads(out or "{}").get("mergeStateStatus") or "").upper()
        if state and state != "UNKNOWN":
            print(f"[rebase-bot] #{num}: merge state resolved to {state} on re-query {attempt}")
            return state
    return "UNKNOWN"




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
    """PR numbers this bot really REBASED today — read from its `bot-done` marker, nothing else.

    The daily record is the only bound on rebasing a PR twice, so it must not be guessed from
    prose: a claim (`bot-claim: … rebase …`), a failure (`gave-up`), another bot's marker and
    another day's marker all leave the PR a candidate (issue #457). The marker comes from each
    candidate PR's comments, because `gh search prs` exposes no comment bodies (issue #309).
    """
    out = _gh(gh, ["search", "prs", "--repo", repo, "--updated", f">={today}",
                   "--json", "number", "--limit", "50"])
    done = []
    for pr in json.loads(out or "[]") or []:
        num = pr.get("number")
        if num is None:
            continue
        if _rebased_marker(_comments(gh, repo, num), today):
            done.append(num)
    return done


def _rebased_marker(comments: list[dict], today: str) -> bool:
    """Does this thread carry THIS bot's `rebased` done marker for `today`?"""
    for comment in comments or []:
        m = bot_claims.DONE_RE.search(comment.get("body") or "")
        if not m:
            continue
        if m.group("bot").lower() != bot_claims.REBASER:
            continue
        if not m.group("at").startswith(today):
            continue
        if (m.group("what") or "").strip().lower() != REBASED_KIND:
            continue
        return True
    return False


def _comments(gh: str, repo: str, num: int) -> list[dict]:
    """This PR's comments — where the claim protocol lives (scripts/bot_claims.py).

    Asked for through `--json` alone: `gh` REFUSES `--comments` together with `--json`.
    """
    out = _gh(gh, ["pr", "view", str(num), "--repo", repo, "--json", "comments"])
    return (json.loads(out or "{}") or {}).get("comments") or []


#: What `gh pr checks` prints to stderr AND exits 1 with when the PR has no checks at all. That is
#: the NORMAL answer for the PR this bot exists to rebase: a conflicted (`DIRTY`) PR gets no CI run,
#: because GitHub cannot build a merge ref for it (issue #801). Reading the exit code as a crash made
#: `make rebase-bot-sweep` die on exactly its own target — measured on run 40700214889:
#:
#:     [rebase-bot] gh pr checks 789 --repo asimov-agent/llgenie --json state failed (1):
#:       no checks reported on the 'agent/issue-772-…' branch
NO_CHECKS = "no checks reported"


def _checks(gh: str, repo: str, num: int) -> tuple[bool, bool]:
    """(is anything still running, is anything red) for this PR, from its checks.

    Both matter for coexisting with the other bots: rebasing cancels an in-flight run, and a
    failing test is the fix-bot's business rather than something a rebase can fix.

    A PR with NO checks is `(False, False)` — not an error. `gh pr checks` exits 1 saying "no checks
    reported" for it, and a conflicted PR cannot have any (issue #801), so a crash there blocked the
    one PR that needed the rebase. Every OTHER non-zero exit is still a hard failure: an unreadable
    answer must never be read as "nothing in flight, nothing red".
    """
    r = subprocess.run([gh, "pr", "checks", str(num), "--repo", repo, "--json", "state"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        if NO_CHECKS in (r.stderr or "").lower():
            print(f"[rebase-bot] #{num}: no checks reported (a conflicted PR has no CI run); "
                  f"reading it as neither in flight nor red")
            return False, False
        raise SystemExit(f"[rebase-bot] gh pr checks {num} --repo {repo} failed "
                         f"({r.returncode}): {r.stderr.strip()}")
    states = [(c.get("state") or "").upper() for c in (json.loads(r.stdout or "[]") or [])]
    running = any(s in ("PENDING", "IN_PROGRESS", "QUEUED", "EXPECTED", "WAITING") for s in states)
    red = any(s in ("FAILURE", "ERROR", "FAIL", "CANCELLED", "TIMED_OUT") for s in states)
    return running, red


#: Sentinel: a `gh` read for ONE PR failed, so that PR could not be judged.
_READ_FAILED = object()


def _read_pr(crashed: list[str], label: str, fn, *args):
    """Call a `gh` read, naming the PR it was about when it fails (issue #801).

    A crashed read used to leave the run with a bare non-zero exit and no mention of the PR it
    stopped, so the PR that needed the rebase was the one thing missing from the log. The failure is
    collected here, printed with the PR, and the scan continues — the caller then reports ALL of
    them and exits non-zero, because a partial scan is not a decision.
    """
    try:
        return fn(*args)
    except SystemExit as exc:
        crashed.append(f"{label}: {exc}")
        print(f"[rebase-bot] ERROR on {label}: {exc}")
        return _READ_FAILED


def sweep(gh: str, repo: str, today: str | None = None, max_per_day: int = MAX_PER_DAY,
          own_fork: str | None = None, unknown_attempts: int = UNKNOWN_ATTEMPTS,
          unknown_delay: float = UNKNOWN_DELAY_S, skip: list[int] | None = None) -> dict:
    """Pick the one PR to rebase, or explain why none is."""
    d = today or _today()
    done = rebased_today(gh, repo, d)
    if len(done) >= max_per_day:
        return {"action": "cap", "pr": None, "reasons": [], "deferred": [],
                "reason": f"already rebased {len(done)}/{max_per_day} PRs today"}
    owner = repo.split("/")[0].lower()
    prs = json.loads(_gh(gh, ["pr", "list", "--repo", repo, "--state", "open", "--limit", "100",
                              "--json", "number,title,isDraft,mergeStateStatus,headRefName,"
                                        "headRepositoryOwner,createdAt,baseRefName"]) or "[]") or []
    reasons = []
    deferred: list[int] = []
    crashed: list[str] = []
    for pr in sorted(prs, key=lambda p: p.get("createdAt") or ""):
        num = pr.get("number")
        label = f"#{num} ({pr.get('headRefName') or 'unknown branch'})"
        head_repo = ((pr.get("headRepositoryOwner") or {}).get("login") or "").lower()
        if pr.get("isDraft"):
            reasons.append(f"#{num} is a draft"); continue
        if (pr.get("baseRefName") or "main") != "main":
            reasons.append(f"#{num} targets {pr.get('baseRefName')}, not main"); continue
        # `done` (today's markers) bounds the daily cap, NOT the eligibility: a PR rebased this
        # morning and re-dirtied by a later merge still needs the rebase, and after a successful
        # one the PR reads CLEAN so it cannot be picked again (issue #467). Only the PRs this run
        # already handled are passed over by number.
        if skip and num in skip:
            reasons.append(f"#{num} was already rebased in this run"); continue
        if head_repo not in (owner, (own_fork or "").lower()):
            reasons.append(f"#{num} lives on {head_repo or 'an unknown repo'} (not pushable here)")
            continue
        state = (pr.get("mergeStateStatus") or "").upper()
        if state == "UNKNOWN":
            # Never decide from an uncomputed merge state (issue #453): re-ask the PR itself.
            state = _read_pr(crashed, label, resolve_state, gh, repo, num, state,
                             unknown_attempts, unknown_delay)
            if not isinstance(state, str):
                continue
        if state not in NEEDS:
            if state == "UNKNOWN":
                deferred.append(num)
                reasons.append(f"#{num} has no computed merge state (UNKNOWN) after "
                               f"{unknown_attempts} re-queries — deferred to the next run")
            else:
                reasons.append(f"#{num} is {state or 'unknown'} against main")
            continue
        # --- coexistence with the other bots: never invalidate a run, never race the fix-bot ---
        # A claim is how the other bot says "I am on this branch" (issue #285): a fix-bot repair
        # spends up to 180 minutes in the agent with nothing in flight and no commit yet, so the
        # checks and the attempt counter both look idle. A claim from ANY other bot makes this PR
        # theirs; a `done` marker releases it, and a claim older than PR_CLAIM_TTL is ignored.
        comments = _read_pr(crashed, label, _comments, gh, repo, num)
        if not isinstance(comments, list):
            continue
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
        checks = _read_pr(crashed, label, _checks, gh, repo, num)
        if not isinstance(checks, tuple):
            continue
        running, red = checks
        if running:
            reasons.append(f"#{num} has checks in flight; rebasing now would cancel that run")
            continue
        if red and state == "BEHIND":
            reasons.append(f"#{num} is red and only behind: the fix-bot owns that, a rebase is not "
                           "the blocker (a conflicted PR is taken, since the rebase is one)")
            continue
        if crashed:
            break                            # a partial scan is not a decision (#801): report it
        return {"action": "rebase", "pr": num, "head_branch": pr.get("headRefName"),
                "head_repo": head_repo or owner, "state": state, "title": pr.get("title"),
                "fingerprint": f"{head_repo}:{pr.get('headRefName')}",
                "reasons": reasons, "deferred": deferred,
                "reason": f"#{num} is {state} against main"}
    if crashed:
        return {"action": "error", "pr": None, "reasons": reasons, "deferred": deferred,
                "crashed": crashed,
                "reason": f"could not read {len(crashed)} PR(s), so no decision was made"}
    return {"action": "none", "pr": None, "reasons": reasons, "deferred": deferred,
            "reason": "no open PR needs rebasing"}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="rebase_bot_sweep")
    p.add_argument("--gh", default="gh")
    p.add_argument("--repo", required=True)
    p.add_argument("--today", default=None)
    p.add_argument("--max-per-day", type=int, default=MAX_PER_DAY)
    p.add_argument("--own-fork", default=None,
                   help="the owner whose fork this bot may push to (e.g. andyholst)")
    p.add_argument("--unknown-attempts", type=int, default=UNKNOWN_ATTEMPTS,
                   help="re-queries for a PR whose merge state GitHub has not computed yet")
    p.add_argument("--unknown-delay", type=float, default=UNKNOWN_DELAY_S,
                   help="seconds between those re-queries")
    p.add_argument("--skip", default="",
                   help="comma-separated PR numbers this run already rebased (never picked twice)")
    a = p.parse_args(argv)
    skip = [int(n) for n in (a.skip or "").replace(" ", "").split(",") if n]
    res = sweep(a.gh, a.repo, a.today, a.max_per_day, a.own_fork,
                a.unknown_attempts, a.unknown_delay, skip)
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
    if res["action"] == "error":
        # Red on stdout as well as the exit code: the workflow prints this before it decides, and a
        # crash that does not name the PR it prevented is what #801 was about.
        for line in res.get("crashed") or []:
            print(f"error={line}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
