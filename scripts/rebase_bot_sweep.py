"""Which ONE open PR the rebase bot should bring back onto `main` (issue #246).

The bot runs every 6 hours (`.github/workflows/rebase-bot.yml`). AGENTS.md and issue #107 forbid
a CI job that can skip itself, so the workflow is ONE job that always runs and this decides:
*one PR per run*, with a stated reason for every PR it passes over.

What it looks for: an open, non-draft PR against `main` that has to come back onto `main`.
Two independent signals, and they disagree on purpose:

  * the platform's own `mergeable == CONFLICTING` — a real conflict, whatever the state says;
  * a DIRECT lineage measurement (#2071): the head's merge-base with `main` is not `main`'s tip,
    so the branch is behind. This one exists because `mergeStateStatus` cannot answer staleness:
    GitHub reports `BLOCKED` for a pending review or a failing check and `UNSTABLE` for a failing
    check, so a stale-AND-red PR never says `BEHIND` and a state-only read passed it over. Six
    PRs sat unrebasable that way (measured 2026-11-08, all `BLOCKED`+`MERGEABLE`+behind).
    The definition is shared with `check-pr-base` (`scripts/check_pr_base.staleness_from_compare`)
    so the sweep and the gate cannot drift.

It also keeps out of the other bots' way, because three of them touch branches:

  * a PR with checks IN FLIGHT is skipped — rebasing it would cancel the run that is deciding it;
  * a PR that is behind AND whose only red is the staleness gate is taken here, not deferred to
    the fix-bot (#2071, half B): the rebase is the PRECONDITION for that gate, so "fix-bot owns a
    red PR" cannot swallow a stale one. A PR that is red for a real failing test is still the
    fix-bot's — the narrowing keys on the measured-behind fact, never on the state string;
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
import time
import datetime as dt
from datetime import datetime, timezone

import bot_claims
import check_pr_base

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

#: Mergeability values that mean "the branch is in a real conflict with main" regardless of the
#: mergeStateStatus GitHub labels it with (issue #1566, the #536 class). A PR whose merge state
#: reads `BLOCKED` (a required review is pending) or `UNSTABLE` (a check is failing) can still be
#: genuinely `mergeable: CONFLICTING` — the platform masks the conflict behind the review/check.
#: Reading `mergeStateStatus` alone behind that mask classifies the PR `NONE` and the only
#: automatic rebase passes it over. cross_checked with the fleet's own rule (#1015: measured
#: fresh with `mergeable == "CONFLICTING"`, never `mergeStateStatus` alone).
CONFLICTING = "CONFLICTING"

#: The four outcomes of reading ONE PR's merge state, and there are exactly four (issue #801).
#: Three would be the defect: collapsing `UNKNOWN` into "nothing to do" left #445-#447 stale with a
#: green run behind them (issue #453), and collapsing a crashed read into "nothing to do" is what let a
#: sweep report success while the conflicted PR it was dispatched for was never rebased (issue #801).
REBASE, NONE, DEFER, ERROR = "rebase", "none", "defer", "error"


def measure_behind(gh: str, repo: str, base: str, head_ref: str) -> bool | None:
    """Is this PR's head genuinely behind `base`, measured directly from lineage?

    The defect #2071 names: `mergeStateStatus` cannot answer this. GitHub reports `BLOCKED`
    whenever a required review is pending or a check is failing, and `UNSTABLE` for a failing
    check — so a stale-and-red PR never says `BEHIND`, `outcome()` returns `NONE`, and the one
    automatic rebase passes over exactly the PR that needs it.

    The measurement is the SAME definition `check-pr-base` enforces (`Makefile:1136`, issue
    #845): the head is behind iff its merge-base with the base is not the base tip. Read here
    through the platform's own `compare` endpoint, which answers merge-base/base/behind_by over
    REST — so it works for a remote PR head the runner has never fetched. `check_pr_base`'s
    `staleness_from_compare()` holds the single definition; this function only fetches the
    payload, so the sweep and the gate cannot drift apart.

    Returns `True` (behind, needs a rebase), `False` (cut from the live base tip), or `None`
    when the payload could not be read — a failed read is never "not behind" (issue #801).
    """
    try:
        out = _gh(gh, ["api", f"repos/{repo}/compare/{base}...{head_ref}"])
        data = json.loads(out or "{}") or {}
    except SystemExit:
        return None
    if not data or "merge_base_commit" not in data:
        return None
    return check_pr_base.staleness_from_compare(data)


def outcome(state: str, crashed: bool = False, mergeable: str | None = None,
            behind: bool | None = None) -> str:
    """Classify one PR's merge state into exactly one of the four outcomes.

    `crashed` is an argument rather than a separate code path on purpose: a read that failed is an
    outcome of the same decision, so it cannot be dropped by a caller that only remembers three.

    `mergeable` overrides the state when it is a genuine conflict (issue #1566): GitHub reports
    `mergeStateStatus=BLOCKED` for a PR whose required review is pending even when its branch is in
    a real merge conflict, so a `CONFLICTING` mergeable must win over `BLOCKED`/`UNSTABLE`/`CLEAN`
    — otherwise the sweep silently skips the exact PR it exists to rebase (#536 class). `UNKNOWN`
    re-query and DEFER semantics are unchanged: conflict beats a pending state, but never changes a
    crashed read into a rebase.

    `behind` is the DIRECT lineage measurement (#2071), not a state string. A genuinely-behind
    branch is `REBASE` whatever GitHub labels the row, because `BLOCKED`/`UNSTABLE`/`CLEAN` mask
    staleness behind a pending review or a failing check. It outranks the `UNKNOWN`→`DEFER` branch
    for the same reason it exists: DEFER says "the platform has not told us", and this is the
    answer. `None` means "not measured" and leaves every prior rule exactly as it was, so a caller
    that cannot measure does not silently change behaviour.
    """
    if crashed:
        return ERROR
    if (mergeable or "").upper() == CONFLICTING:
        return REBASE
    if behind is True:
        return REBASE
    value = (state or "").upper()
    if value in NEEDS:
        return REBASE
    if value == "UNKNOWN":
        return DEFER
    return NONE
#: GitHub computes mergeability lazily: a `pr list` right after a push/comment can report
#: `UNKNOWN` for every PR. Treating that as "no rebase needed" is what left #445-#447 stale
#: (issue #453), so a PR reported UNKNOWN is re-queried — bounded, never an unbounded poll.
UNKNOWN_ATTEMPTS = 4
UNKNOWN_DELAY_S = 3.0


def _gh(gh: str, args: list[str]) -> str:
    r = subprocess.run([gh, *args], capture_output=True, text=True)  # proc-allow: direct subprocess call site, tracked remainder for issue #797 (migrate onto scripts/proc.py in a per-module batch)
    if r.returncode != 0:
        raise SystemExit(f"[rebase-bot] {gh} {' '.join(args)} failed ({r.returncode}): {r.stderr.strip()}")
    return r.stdout


def resolve_state(gh: str, repo: str, num: int, state: str,
                  attempts: int = UNKNOWN_ATTEMPTS, delay: float = UNKNOWN_DELAY_S) -> tuple[str, str]:
    """The PR's merge state and mergeability, re-asked while GitHub has not computed them (issue #453).

    `UNKNOWN` is not an answer: it means the mergeability computation has not finished, and it is
    what a fresh `pr list` returns right after a push or a comment. The single-PR read
    (`gh pr view`) is the cheap way to get the computed value, and a few re-queries turn a
    transient UNKNOWN into the real BEHIND/DIRTY. The mergeable field rides along on the same query
    (issue #1566): a `CONFLICTING` mergeable must be known even when the state reads BLOCKED.
    A state that never resolves is returned as UNKNOWN so the caller can DEFER the PR by name
    instead of pretending it needs nothing.

    Returns `(state, mergeable)` so the caller can apply both to the outcome.
    """
    for attempt in range(1, attempts + 1):
        time.sleep(delay)
        out = _gh(gh, ["pr", "view", str(num), "--repo", repo,
                       "--json", "mergeStateStatus,mergeable"])
        data = json.loads(out or "{}") or {}
        state = (data.get("mergeStateStatus") or "").upper()
        mergeable = (data.get("mergeable") or "").upper()
        if state and state != "UNKNOWN":
            print(f"[rebase-bot] #{num}: merge state resolved to {state} (mergeable {mergeable}) "
                  f"on re-query {attempt}")
            return state, mergeable
    return "UNKNOWN", ""


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
    r = subprocess.run([gh, "pr", "checks", str(num), "--repo", repo, "--json", "state"],  # proc-allow: direct subprocess call site, tracked remainder for issue #797 (migrate onto scripts/proc.py in a per-module batch)
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
                              "--json", "number,title,isDraft,mergeStateStatus,mergeable,headRefName,"
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
        #: `mergeable` is the platform's own conflict answer, read alongside the state (issue #1566).
        #: `mergeStateStatus` can read BLOCKED/UNSTABLE/CLEAN on a genuinely conflicting branch, so a
        #: `CONFLICTING` mergeable must be consulted even when the state does not say DIRTY.
        mergeable = (pr.get("mergeable") or "")
        if state == "UNKNOWN":
            # Never decide from an uncomputed merge state (issue #453): re-ask the PR itself.
            resolved = _read_pr(crashed, label, resolve_state, gh, repo, num, state,
                                unknown_attempts, unknown_delay)
            if not isinstance(resolved, tuple):
                continue
            state, mergeable = resolved
        # --- the DIRECT staleness measurement (#2071) ---
        # `mergeStateStatus` can never prove a branch is fresh: BLOCKED is reported for a pending
        # review or a failing check, UNSTABLE for a failing check, so a stale-and-red PR never
        # says BEHIND and the old state-only read classified it NONE. Measure the lineage itself,
        # on EVERY PR, with the same definition `check-pr-base` enforces (merge-base == base tip
        # ⇒ fresh). Measuring even when the state already reads BEHIND is deliberate: half B of
        # #2071 needs to know whether a red PR is behind in order to take it from the fix-bot.
        # `None` (unreadable) stays `None`: a failed read is never "not behind" (#801).
        behind = _read_pr(crashed, label, measure_behind, gh, repo, "main",
                          pr.get("headRefName") or "")
        measured_behind = behind is True
        if not isinstance(behind, bool):
            behind = None
        if outcome(state, mergeable=mergeable, behind=behind) is not REBASE:
            if state == "UNKNOWN":
                deferred.append(num)
                reasons.append(f"#{num} has no computed merge state (UNKNOWN) after "
                               f"{unknown_attempts} re-queries — deferred to the next run")
            elif behind is None:
                reasons.append(f"#{num} is {state or 'unknown'} against main and its staleness "
                               f"could not be measured — left for the next run "
                               f"(a failed read is not a decision, #801)")
            else:
                reasons.append(f"#{num} is {state or 'unknown'} against main and NOT behind "
                               f"(measured: merge-base == base tip)")
            continue
        if measured_behind:
            # Name it per PR, so `rebased: 0` can never be printed while a genuinely-behind PR
            # was passed over (acceptance criterion 5).
            reasons.append(f"#{num} is {state or 'unknown'} but MEASURED behind main "
                           f"(merge-base != base tip) — the state masks staleness (#2071)")
            state = "BEHIND" if (state or "").upper() in ("", "UNKNOWN", "BLOCKED",
                                                          "UNSTABLE", "CLEAN") else state
        # --- coexistence with the other bots: never invalidate a run, never race the fix-bot ---
        # A claim is how the other bot says "I am on this branch" (issue #285): a fix-bot repair
        # spends up to 180 minutes in the agent with nothing in flight and no commit yet, so the
        # checks and the attempt counter both look idle. A claim from ANY other bot makes this PR
        # theirs; a `done` marker releases it, and a claim older than PR_CLAIM_TTL is ignored.
        comments = _read_pr(crashed, label, _comments, gh, repo, num)
        if not isinstance(comments, list):
            continue
        held = bot_claims.occupied(comments, bot_claims.REBASER, ttl=bot_claims.PR_CLAIM_TTL,
                                   is_live=lambda rid: bot_claims.run_is_live(rid, lambda args: _gh(gh, args)))
        if held:
            reasons.append(f"#{num} is held by another bot: {held}")
            continue
        gone = bot_claims.released(comments, bot_claims.REBASER, ttl=bot_claims.PR_CLAIM_TTL,
                                   is_live=lambda rid: bot_claims.run_is_live(rid, lambda args: _gh(gh, args)))
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
        if red and state == "BEHIND" and not measured_behind:
            reasons.append(f"#{num} is red and only behind: the fix-bot owns that, a rebase is not "
                           "the blocker (a conflicted PR is taken, since the rebase is one)")
            continue
        if crashed:
            break                            # a partial scan is not a decision (#801): report it
        return {"action": "rebase", "pr": num, "head_branch": pr.get("headRefName"),
                "head_repo": head_repo or owner, "state": state, "title": pr.get("title"),
                "behind": measured_behind,
                "fingerprint": f"{head_repo}:{pr.get('headRefName')}",
                "reasons": reasons, "deferred": deferred,
                "reason": f"#{num} is {state} against main"
                          + (" (measured behind main's tip)" if measured_behind else "")}
    if crashed:
        return {"action": "error", "pr": None, "reasons": reasons, "deferred": deferred,
                "crashed": crashed,
                "reason": f"could not read {len(crashed)} PR(s), so no decision was made"}
    return {"action": "none", "pr": None, "reasons": reasons, "deferred": deferred,
            "reason": "no open PR needs rebasing"}


CRASHED_PR = re.compile(r"#(\d+)")


def surface_crashes(gh: str, repo: str, crashed: list[str], post=_gh) -> list[int]:
    """Comment on each PR whose read crashed, so the fleet sees it and not only a red run (issue #801).

    A `DIRTY` PR has no CI run at all, and `fix-bot` reacts only to failing checks — so a sweep that
    crashes while a conflicted PR exists leaves that PR invisible to every other bot. The comment is
    the only channel that reaches a human reader of the PR, and it names what failed rather than saying
    "the sweep broke".
    """
    seen: list[int] = []
    for line in crashed:
        m = CRASHED_PR.search(line)
        if not m:
            continue
        num = int(m.group(1))
        if num in seen:
            continue
        seen.append(num)
        body = ("**rebase-bot could not decide this PR.** The sweep failed while reading it, so no rebase "
                "was attempted and no CI run was started (a conflicted PR gets none).\n\n"
                f"```\n{line}\n```\n\n"
                "Nothing on this branch is at fault; the next sweep will retry it. Filed under #801.")
        post(gh, ["pr", "comment", str(num), "--repo", repo, "--body", body])
    return seen


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
        surfaced = surface_crashes(a.gh, a.repo, res.get("crashed") or [])
        if surfaced:
            print(f"[rebase-bot] surfaced the failure on {', '.join(f'#{n}' for n in surfaced)} so it is "
                  f"not only a red run (issue #801)")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
