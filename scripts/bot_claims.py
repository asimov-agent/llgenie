"""Which bot, if any, is already working an issue (issues #261, #263).

A bot that is about to REFINE or IMPLEMENT an issue says so ON THE ISSUE, before it starts, with a
machine-readable marker:

    <!-- bot-claim: refiner 2026-10-14T22:10:03Z refine -->

Any other bot reads the issue's comments and stands down while a claim from a DIFFERENT bot is
still fresh. That is the whole concurrency rule: no bot has to know another's schedule, and the
schedules stop being the race protection (which is why the refiner can run hourly while the
implementer runs daily).

A claim older than CLAIM_TTL is ignored, so a run that died leaves no lock behind.

Shared byte-identically by `scripts/issue_refiner.py` and `scripts/issue_implementer.py`.
"""
from __future__ import annotations

import datetime as dt
import re

#: How long a claim holds. Longer than the longest bot run (the agent jobs are budgeted for an
#: hour), short enough that a crashed run does not block the backlog for a day.
CLAIM_TTL = dt.timedelta(hours=3)

DONE_RE = re.compile(
    r"<!--\s*bot-done:\s*(?P<bot>[A-Za-z0-9_.-]+)\s+(?P<at>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)"
    r"\s*(?P<what>[A-Za-z-]*)?")

CLAIM_RE = re.compile(
    r"<!--\s*bot-claim:\s*(?P<bot>[A-Za-z0-9_.-]+)\s+(?P<at>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)"
    r"\s+(?P<work>refine|implement)\s*-->")

#: The bots, as they name themselves in a claim.
REFINER = "refiner"
IMPLEMENTER = "implementer"


#: A `done` marker means one of these. Kept as words, because the difference decides whether the
#: next bot may take the issue: `refined` and `closed`/`merged` release it, while a PR that is
#: implemented but NOT YET APPROVED still occupies it (`pr-open`) - nobody should start a second
#: implementation of an issue whose PR is sitting in review.
DONE_RELEASES = ("refined", "closed", "merged", "done", "rejected")
DONE_OCCUPIES = ("pr-open", "implemented")


def done_comment(bot: str, when: dt.datetime, what: str = "done") -> str:
    """The release: posted when the work the claim announced is FINISHED.

    Without it the issue stays occupied until the claim expires, so every bot that claims has to
    close its own claim - the maintainer's rule is "a recent comment that has NOT been set done
    with a comment means someone is on it".
    """
    stamp = when.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return f"<!-- bot-done: {bot} {stamp} {what} -->"


def claim_comment(bot: str, work: str, when: dt.datetime) -> str:
    """The claim to post BEFORE starting, so another bot can see the issue is taken."""
    assert work in ("refine", "implement"), work
    stamp = when.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return (f"<!-- bot-claim: {bot} {stamp} {work} -->\n"
            f"`{bot}` is {work}ing this issue now. Other bots: leave it alone for the next "
            f"{int(CLAIM_TTL.total_seconds() // 3600)} hours.")


def claims(comments: list[dict] | None) -> list[dict]:
    """Every claim in the thread, oldest first. An unparseable marker is ignored, never fatal."""
    out: list[dict] = []
    for c in comments or []:
        m = CLAIM_RE.search((c.get("body") or ""))
        if not m:
            continue
        try:
            at = dt.datetime.strptime(m.group("at"), "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=dt.timezone.utc)
        except ValueError:
            continue
        out.append({"bot": m.group("bot").lower(), "at": at, "work": m.group("work")})
    return sorted(out, key=lambda c: c["at"])


def occupant(comments: list[dict] | None, bot: str, now: dt.datetime | None = None,
             ttl: dt.timedelta = CLAIM_TTL) -> dict | None:
    """The freshest claim by ANOTHER bot, or None. A stale claim locks nothing."""
    now = now or dt.datetime.now(dt.timezone.utc)
    fresh = [c for c in claims(comments)
             if c["bot"] != bot.lower()
             and c["at"] <= now + dt.timedelta(minutes=5)
             and now - c["at"] <= ttl]
    return max(fresh, key=lambda c: c["at"]) if fresh else None


def _at(comment: dict) -> dt.datetime | None:
    """When the comment was posted: its createdAt, else the stamp inside a marker."""
    raw = comment.get("createdAt")
    for cand in (raw, *(m.group("at") for m in (CLAIM_RE.search(comment.get("body") or ""),
                                                DONE_RE.search(comment.get("body") or ""))
                       if m)):
        if not cand:
            continue
        try:
            return dt.datetime.strptime(str(cand)[:19], "%Y-%m-%dT%H:%M:%S").replace(
                tzinfo=dt.timezone.utc)
        except ValueError:
            continue
    return None


def _is_done(comment: dict) -> bool:
    return bool(DONE_RE.search(comment.get("body") or ""))


def occupied(comments: list[dict] | None, bot: str, now: dt.datetime | None = None,
             ttl: dt.timedelta = CLAIM_TTL) -> str | None:
    """A reason to SKIP THIS ISSUE AND TAKE THE NEXT ONE, or None.

    The rule: a recent comment that has not been concluded by a `done` comment means another actor
    is on the issue. So the newest non-self comment decides - a claim (or any bot comment) locks it
    for `ttl`, and a newer `done` releases it. A claim from THIS bot does not lock this bot out.
    """
    now = now or dt.datetime.now(dt.timezone.utc)
    mine = bot.lower()
    newest = None
    for c in comments or []:
        at = _at(c)
        if at is None or at > now + dt.timedelta(minutes=5):
            continue
        marker = CLAIM_RE.search(c.get("body") or "")
        if marker and marker.group("bot").lower() == mine:
            continue                      # my own claim: my issue
        dm = DONE_RE.search(c.get("body") or "")
        if newest is None or at >= newest["at"]:
            newest = {"at": at, "done": bool(dm),
                      "kind": (dm.group("what") or "").strip().lower() if dm else "",
                      "who": (marker.group("bot") if marker else None)
                             or ((c.get("author") or {}).get("login") or "someone"),
                      "work": marker.group("work") if marker else None}
    if not newest:
        return None
    age = now - newest["at"]
    if newest["done"]:
        kind = newest["kind"]
        if kind in DONE_OCCUPIES:
            return (f"{newest['who']} finished this as `{kind}` - a PR is open and not merged, "
                    f"so leave it to review")
        return None                       # concluded: refined, closed or merged
    if age > ttl:
        return None                       # stale: a crashed run must not hold the backlog
    minutes = int(age.total_seconds() // 60)
    if newest["work"]:
        return f"claimed by {newest['who']} to {newest['work']} it {minutes} min ago"
    return f"commented on by {newest['who']} {minutes} min ago without a done comment"
