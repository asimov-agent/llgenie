"""Which bot, if any, is already working a subject (issues #261, #263, #279, #285, #291, #292).

A bot that is about to REFINE, IMPLEMENT, repair or REBASE says so ON THE SUBJECT, before it starts,
with a machine-readable marker that now carries its own terms:

    <!-- bot-claim: refiner 2026-10-14T22:10:03Z refine ttl=180m run=123456 -->

Any other bot reads the subject's comments and stands down while a claim from a DIFFERENT bot still
holds. That is the whole concurrency rule: no bot has to know another's schedule, and the schedules
stop being the race protection (which is why the refiner can run hourly while the implementer runs
daily).

Two properties the marker itself carries, because a reader applying its OWN numbers made both
decorative (#292) and a claim from a run that died held for the whole TTL (#291):

* **`ttl=<minutes>m`** — how long the writer says this work may take. The reader honours THAT, and
  falls back to its own default only for a legacy marker (written before this field existed). Before,
  a rebase's 30-minute claim blocked a 4-hour reader, and the sentence a maintainer read ("leave it
  alone for 4 hours") disagreed with what the bots actually did.
* **`run=<id>`** — the workflow run holding it. A reader that can ask GitHub (`is_live=`) releases the
  subject the moment that run is finished/cancelled, so a cancelled run does not freeze a PR for the
  whole TTL. `released()` then says so out loud; the skip is never silent.

An unparseable marker is ignored, never fatal, and an unreadable run state is `None` — "we could not
check" must never release a claim.

Shared byte-identically by `scripts/issue_refiner.py`, `scripts/issue_implementer.py`,
`scripts/fix_bot_sweep.py` and `scripts/rebase_bot_sweep.py`.
"""
from __future__ import annotations

import datetime as dt
import json
import re

#: How long a claim holds when the marker does not say. Longer than the longest bot run (the agent
#: jobs are budgeted for an hour), short enough that a crashed run does not block the backlog a day.
CLAIM_TTL = dt.timedelta(hours=3)

DONE_RE = re.compile(
    r"<!--\s*bot-done:\s*(?P<bot>[A-Za-z0-9_.-]+)\s+(?P<at>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)"
    r"\s*(?P<what>[A-Za-z-]*)?")

#: A claim marker. `ttl=` and `run=` are optional so a marker written before #292 still parses; the
#: reader then falls back to its own default TTL and cannot check liveness.
CLAIM_RE = re.compile(
    r"<!--\s*bot-claim:\s*(?P<bot>[A-Za-z0-9_.-]+)\s+(?P<at>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)"
    r"\s+(?P<work>refine|implement|fix|rebase|clean)"
    r"(?:\s+ttl=(?P<ttl>\d+)m)?"
    r"(?:\s+run=(?P<run>\d+))?\s*-->")

#: The bots, as they name themselves in a claim. The first two work on issues, the last two on PRs;
#: the name is the workflow's bot name (`fix-bot.yml` -> `fix-bot`) so a claim reads as the thing a
#: maintainer sees in the Actions tab.
REFINER = "refiner"
IMPLEMENTER = "implementer"
FIXER = "fix-bot"
REBASER = "rebase-bot"
CLEANER = "issue-cleaner"

#: How long a PR claim holds when the marker does not say. The fix-bot's own budget is 180 minutes
#: (three rounds of check + agent repair), so a reader must age a claim by at least that or the
#: rebase-bot walks in mid-repair.
PR_CLAIM_TTL = dt.timedelta(hours=4)


#: A `done` marker means one of these. Kept as words, because the difference decides whether the
#: next bot may take the subject: `refined` and `closed`/`merged` release it, while a PR that is
#: implemented but NOT YET APPROVED still occupies it (`pr-open`) - nobody should start a second
#: implementation of an issue whose PR is sitting in review. `cancelled`/`gave-up`/`repaired` are
#: the outcomes a run posts when it stops without finishing, so an abandoned subject is released by
#: an explicit statement instead of only by the TTL (#291).
DONE_RELEASES = ("refined", "closed", "merged", "done", "rejected", "cancelled", "gave-up",
                 "repaired")
DONE_OCCUPIES = ("pr-open", "implemented")


def _stamp(when: dt.datetime) -> str:
    return when.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _say(ttl: dt.timedelta) -> str:
    """A duration as a human reads it, in the unit that is true (minutes under two hours)."""
    minutes = int(round(ttl.total_seconds() // 60))
    if minutes < 120:
        return f"{minutes} minute{'s' if minutes != 1 else ''}"
    hours = int(round(minutes / 60))
    return f"{hours} hour{'s' if hours != 1 else ''}"


def done_comment(bot: str, when: dt.datetime, what: str = "done") -> str:
    """The release: posted when the work the claim announced is FINISHED (or abandoned).

    Without it the subject stays occupied until the claim expires, so every bot that claims has to
    close its own claim - the maintainer's rule is "a recent comment that has NOT been set done
    with a comment means someone is on it".
    """
    return f"<!-- bot-done: {bot} {_stamp(when)} {what} -->"


def claim_comment(bot: str, work: str, when: dt.datetime, ttl: dt.timedelta | None = None,
                  run_id: int | str | None = None) -> str:
    """The claim to post BEFORE starting, so another bot can see the subject is taken.

    The marker carries the terms a READER applies: `ttl=` (how long this work may take) and `run=`
    (which run holds it, so a reader can see it end). The sentence a human reads is built from the
    same `ttl`, so the two can no longer disagree (#292).
    """
    assert work in ("refine", "implement", "fix", "rebase", "clean"), work
    window = ttl or CLAIM_TTL
    marker = f"<!-- bot-claim: {bot} {_stamp(when)} {work} ttl={int(window.total_seconds() // 60)}m"
    if run_id:
        marker += f" run={int(run_id)}"
    return (marker + " -->\n"
            f"`{bot}` is {work}ing this now. Other bots: leave it alone for the next "
            f"{_say(window)}.")


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
        out.append({"bot": m.group("bot").lower(), "at": at, "work": m.group("work"),
                    "ttl": dt.timedelta(minutes=int(m.group("ttl"))) if m.group("ttl") else None,
                    "run": int(m.group("run")) if m.group("run") else None})
    return sorted(out, key=lambda c: c["at"])


def run_is_live(gh_call, run_id: int, ) -> bool | None:
    """Whether the run that posted a claim is still going: True, False, or None when unknowable.

    `gh_call(args)` is the CALLER's own gh runner, so this module never shells out and stays
    testable. None means the state could not be read (unknown id, a CLI failure, a shape we do not
    recognise) and must NEVER release a claim: "we could not check" is not "it is gone".
    """
    try:
        data = json.loads(gh_call(["run", "view", str(run_id), "--json", "status,conclusion"]) or "{}")
    except Exception:  # noqa: BLE001 - any failure means unknown, never dead
        return None
    if not isinstance(data, dict):
        return None
    status = str(data.get("status") or "").strip().lower()
    if status == "completed":
        return False
    if status in ("queued", "in_progress", "pending", "requested", "waiting"):
        return True
    return None


def occupant(comments: list[dict] | None, bot: str, now: dt.datetime | None = None,
             ttl: dt.timedelta = CLAIM_TTL, is_live=None) -> dict | None:
    """The freshest claim by ANOTHER bot that still HOLDS, or None."""
    dec = _decide(comments, bot, now, ttl, is_live)
    return dec if dec and dec["hold"] and dec["work"] else None


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


def _decide(comments: list[dict] | None, bot: str, now: dt.datetime | None = None,
            ttl: dt.timedelta = CLAIM_TTL, is_live=None) -> dict | None:
    """The newest non-self comment and what it means: does it HOLD the subject, and why not.

    A claim holds while it is fresher than the TTL ITS OWN MARKER announced (the caller's `ttl` is
    the fallback for a legacy marker) and, when the marker names a run and the caller can ask,
    while that run is still going. A `done` comment decides by its outcome word instead.
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
            continue                      # my own claim: my subject
        dm = DONE_RE.search(c.get("body") or "")
        if not marker and not dm:
            continue                      # a plain comment holds nothing: only a claim marker does
        if newest is None or at >= newest["at"]:
            newest = {"at": at, "done": bool(dm),
                      "kind": (dm.group("what") or "").strip().lower() if dm else "",
                      "who": (marker.group("bot") if marker else None)
                             or ((c.get("author") or {}).get("login") or "someone"),
                      "work": marker.group("work") if marker else None,
                      "run": int(marker.group("run")) if marker and marker.group("run") else None,
                      "announced": (dt.timedelta(minutes=int(marker.group("ttl")))
                                    if marker and marker.group("ttl") else None),
                      "hold": True, "why": ""}
    if not newest:
        return None

    age = now - newest["at"]
    if newest["done"]:
        kind = newest["kind"]
        if kind in DONE_OCCUPIES:
            newest["why"] = (f"{newest['who']} finished this as `{kind}` - a PR is open and not "
                             f"merged, so leave it to review")
        else:
            newest["hold"] = False          # concluded: refined, closed, merged, cancelled...
        return newest

    window = newest["announced"] or ttl
    if age > window:
        # #292: the writer's number is the one that binds, and the reader says which one it used.
        newest["hold"] = False
        newest["why"] = (f"the claim announced {_say(window)} and that has passed"
                         if newest["announced"] else f"it is older than {_say(window)}")
        return newest
    if newest["run"] and is_live is not None:
        live = is_live(newest["run"])
        if live is False:
            # #291: the run that held it is over (cancelled, killed, out of budget) - the subject
            # is free NOW, and the reader says so instead of waiting out the TTL in silence.
            newest["hold"] = False
            newest["why"] = f"its run {newest['run']} is no longer running"
            return newest
    return newest


def occupied(comments: list[dict] | None, bot: str, now: dt.datetime | None = None,
             ttl: dt.timedelta = CLAIM_TTL, is_live=None) -> str | None:
    """A reason to SKIP THIS SUBJECT AND TAKE THE NEXT ONE, or None.

    The rule: a recent comment that has not been concluded by a `done` comment means another actor
    is on the subject. The newest non-self comment decides - a claim (or any bot comment) holds it
    for the TTL its marker announced (the caller's `ttl` for a legacy marker) and, when the caller
    can ask, only while the run it names is still going. A claim from THIS bot does not lock this
    bot out.
    """
    now = now or dt.datetime.now(dt.timezone.utc)
    dec = _decide(comments, bot, now, ttl, is_live)
    if not dec or not dec["hold"]:
        return None
    minutes = int((now - dec["at"]).total_seconds() // 60)
    if dec["why"]:
        return dec["why"]
    if dec["work"]:
        return f"claimed by {dec['who']} to {dec['work']} it {minutes} min ago"
    return f"commented on by {dec['who']} {minutes} min ago without a done comment"


def released(comments: list[dict] | None, bot: str, now: dt.datetime | None = None,
             ttl: dt.timedelta = CLAIM_TTL, is_live=None) -> str | None:
    """Why the newest non-self comment does NOT hold any more, or None when there is nothing to say.

    This is the loud half of #291: a subject whose holder is gone is not silently skipped-and-ignored
    by the next bot, the next bot states that it is taking over and what happened to the holder.
    """
    dec = _decide(comments, bot, now, ttl, is_live)
    if not dec or dec["hold"] or dec["done"]:
        return None                          # nothing, still held, or concluded normally
    return (f"{dec['who']} is no longer on this: {dec['why']} - taking it over")
