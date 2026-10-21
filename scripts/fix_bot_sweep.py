"""Pick the red PR a fix-bot sweep should repair (issue #222).

The repo's rule (issue #107, `tests/test_ci_images.py::test_no_ci_step_or_job_is_skipped`) is
that a CI job must not carry a condition that skips it — the decision belongs in `make`. So the
fix-bot is not dispatched by a conditional job inside `ci.yml`; a scheduled sweep asks this
module which PR deserves the bot, under the caps, and only then dispatches:

  * open, non-draft PRs whose head is this repository OR the allowlisted fork (`--own-fork`), which
    is the only other remote the bot's token can push to (issue #340),
  * not `main`,
  * at least one failing check,
  * fewer than `--max-attempts` (default 3) `fix(bot):` commits already on the branch,

best (oldest-updated) first, one PR per sweep. `--dry` prints the decision and dispatches
nothing; both modes read GitHub through `gh`, which tests stub on `PATH` like the repo's other
tests do.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bot_claims  # the shared protocol (issue #279)
import subprocess
import sys

BOT_PREFIX = "fix(bot):"


def _gh(args: list[str]) -> str:
    """One `gh` call, its stdout. Raises with the real stderr when gh fails."""
    r = subprocess.run(["gh", *args], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args)} failed: {r.stderr.strip()}")
    return r.stdout




#: Cache of the liveness probe: one lookup per run id per process (scripts/bot_claims.py, #291).
_LIVE: dict[int, "bool | None"] = {}


def run_is_live(repo: str, run_id: int) -> "bool | None":
    """Whether the run that posted a claim is still going (cached).

    A cancelled/preempted run must not hold a subject for the rest of the claim's TTL (#291): the
    marker carries the run, and this asks GitHub about it. Unknown stays unknown - it never
    releases a claim.
    """
    if run_id not in _LIVE:
        _LIVE[run_id] = bot_claims.run_is_live(lambda args: _gh(args), run_id)
    return _LIVE[run_id]


def open_prs(repo: str) -> list[dict]:
    """Every open PR with the fields the decision needs (one API call)."""
    out = _gh(["pr", "list", "--repo", repo, "--state", "open", "--limit", "100",
               "--json", "number,title,isDraft,headRefName,headRepositoryOwner,updatedAt"])
    return json.loads(out or "[]")


def failing_checks(repo: str, pr: int) -> list[str]:
    """The names of this PR's failing checks (empty = nothing red)."""
    out = _gh(["pr", "checks", str(pr), "--repo", repo, "--json",
               "name,state,bucket,workflow"]).strip()
    if not out:
        return []
    rows = json.loads(out)
    return [r["name"] for r in rows
            if (r.get("bucket") or r.get("state", "")).lower() in ("fail", "failure", "error")]


def bot_attempts(repo: str, pr: int) -> int:
    """How many `fix(bot):` commits the branch already carries (the attempt counter)."""
    out = _gh(["pr", "view", str(pr), "--repo", repo, "--json", "commits"])
    commits = json.loads(out).get("commits") or []
    return sum(1 for c in commits if (c.get("messageHeadline") or "").startswith(BOT_PREFIX))


#: This bot, as the claim marker names it (scripts/bot_claims.py).
FIX_BOT = bot_claims.FIXER   # one name source for every bot


def occupied(repo: str, pr: dict) -> str | None:
    """A reason to leave this PR alone, or None: the claim protocol (issue #279).

    A bot that is going to work a PR says so on it first, and any recent comment that has NOT been
    concluded by a `done` comment means someone is on it - so this sweep skips THAT PR and takes the
    next one, rather than racing whoever is already there.
    """
    out = _gh(["pr", "view", str(pr["number"]), "--repo", repo, "--json", "comments"])
    comments = (json.loads(out or "{}") or {}).get("comments")
    # PR_CLAIM_TTL, not the default: that is the FALLBACK for a marker written before #292, which
    # carries its own ttl. A repair can run 180 minutes, so a claim younger than that is a bot
    # still working, not a stale one (scripts/bot_claims.py).
    why = bot_claims.occupied(comments, FIX_BOT, ttl=bot_claims.PR_CLAIM_TTL,
                              is_live=lambda rid: run_is_live(repo, rid))
    if why:
        return why
    gone = bot_claims.released(comments, FIX_BOT, ttl=bot_claims.PR_CLAIM_TTL,
                               is_live=lambda rid: run_is_live(repo, rid))
    if gone:
        # #291: say it out loud - the PR is free because its holder is GONE, not because it idled.
        print(f"[sweep] #{pr['number']}: {gone}")
    return None


def claim(repo: str, pr: dict) -> None:
    """Say we are starting, before the loop does - in the marker the other bots read."""
    _gh(["pr", "comment", str(pr["number"]), "--repo", repo, "--body",
         bot_claims.claim_comment(FIX_BOT, "fix", datetime.now(timezone.utc),
                                  ttl=bot_claims.PR_CLAIM_TTL,
                                  run_id=os.environ.get("GITHUB_RUN_ID"))])


def eligible(repo: str, pr: dict, max_attempts: int = 3, own_fork: str | None = None) -> tuple[bool, str]:
    """(would the bot run for this PR, why not). Every rule is a plain reason string."""
    head = pr.get("headRepositoryOwner") or {}
    owner = head.get("login") if isinstance(head, dict) else str(head)
    repo_owner = repo.split("/")[0]
    pushable = {repo_owner.lower()}
    if own_fork:
        pushable.add(own_fork.lower())
    if pr.get("isDraft"):
        return False, "draft"
    if pr.get("headRefName") in ("main", "master"):
        return False, "the base branch"
    if owner and owner.lower() not in pushable:
        return False, f"a fork ({owner})"
    if not failing_checks(repo, pr["number"]):
        return False, "no failing check"
    why = occupied(repo, pr)
    if why:
        return False, why
    tries = bot_attempts(repo, pr["number"])
    if tries >= max_attempts:
        return False, f"the cap ({tries}/{max_attempts} attempts)"
    return True, f"{tries + 1}/{max_attempts}: {', '.join(failing_checks(repo, pr['number']))}"


def choose(repo: str, max_attempts: int = 3,
           own_fork: str | None = None) -> tuple[dict | None, list[tuple[dict, str]]]:
    """The first eligible PR (oldest-updated first) and the reasons the others were skipped."""
    prs = sorted(open_prs(repo), key=lambda p: p.get("updatedAt") or "")
    skipped: list[tuple[dict, str]] = []
    for pr in prs:
        ok, why = eligible(repo, pr, max_attempts, own_fork)
        if ok:
            return pr, skipped
        skipped.append((pr, why))
    return None, skipped


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", required=True, help="owner/name")
    ap.add_argument("--max-attempts", type=int, default=3, help="fix(bot): commits per PR")
    ap.add_argument("--check", default="make ci-unit", help="the check the bot drives")
    ap.add_argument("--own-fork", default=None,
                    help="the fork owner this bot may push to (e.g. andyholst)")
    ap.add_argument("--dry", action="store_true", help="decide and print; dispatch nothing")
    a = ap.parse_args(argv)

    pr, skipped = choose(a.repo, a.max_attempts, a.own_fork)
    if pr is not None and not a.dry:
        # Say we are starting, on the PR itself, before the loop runs (issue #279): the other
        # bots read every claim before they pick anything.
        claim(a.repo, pr)
    for p, why in skipped:
        print(f"[sweep] skip #{p['number']} ({p['title'][:60]}): {why}", flush=True)
    if pr is None:
        print(f"[sweep] nothing to fix among {len(skipped)} open PR(s)", flush=True)
        return 0
    print(f"[sweep] #{pr['number']} ({pr['title'][:60]}) on {pr['headRefName']}", flush=True)
    if a.dry:
        print("[sweep] --dry: nothing dispatched", flush=True)
        return 0
    r = subprocess.run(["gh", "workflow", "run", "fix-bot.yml", "--repo", a.repo,
                        "-f", f"pr_number={pr['number']}", "-f", f"branch={pr['headRefName']}",
                        "-f", f"check={a.check}", "-f", f"rounds={a.max_attempts}"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(f"[sweep] dispatch failed: {r.stderr.strip()}", file=sys.stderr, flush=True)
        return 1
    print(f"[sweep] dispatched the fix-bot for #{pr['number']}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
