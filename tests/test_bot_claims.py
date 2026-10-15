"""One claim protocol for every bot (issues #261, #263, #279, #285).

A claim is a comment on the SUBJECT a bot is about to mutate - an issue, or a PR - and every other
bot reads it before it picks anything. This file pins the protocol itself: the vocabulary (the two
issue verbs, the two PR verbs), the TTL a reader applies, and the release.
"""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import bot_claims  # noqa: E402

# occupied() ages a claim against the wall clock and ignores a comment stamped in the future
# (clock-skew tolerance), so the fixtures start half an hour ago.
NOW = dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=30)


def _c(body: str, at: dt.datetime) -> dict:
    return {"body": body, "createdAt": at.isoformat().replace("+00:00", "Z")}


def test_every_bot_that_marks_a_subject_has_a_name_here():
    assert (bot_claims.REFINER, bot_claims.IMPLEMENTER, bot_claims.FIXER, bot_claims.REBASER) == (
        "refiner", "implementer", "fix-bot", "rebase-bot")


def test_the_four_verbs_are_legal_and_anything_else_is_refused():
    """The marker is read by other bots, so an invented verb must not enter it."""
    for bot, work in ((bot_claims.REFINER, "refine"), (bot_claims.IMPLEMENTER, "implement"),
                      (bot_claims.FIXER, "fix"), (bot_claims.REBASER, "rebase")):
        assert bot_claims.claim_comment(bot, work, NOW).startswith(f"<!-- bot-claim: {bot} ")
    try:
        bot_claims.claim_comment(bot_claims.FIXER, "polish", NOW)
    except AssertionError:
        pass
    else:
        raise AssertionError("a made-up work word must be refused, not written into a marker")


def test_a_pr_claim_outlives_a_repair_that_is_still_running():
    """The fix-bot's budget is 180 minutes; a claim that expires under the work it announces would
    hand the branch to the rebase-bot mid-repair."""
    assert bot_claims.PR_CLAIM_TTL > dt.timedelta(minutes=180)
    assert "4 hours" in bot_claims.claim_comment(bot_claims.FIXER, "fix", NOW, ttl=bot_claims.PR_CLAIM_TTL)


def test_a_fresh_repair_holds_the_pr_and_a_done_marker_releases_it():
    """The round trip the rebase-bot relies on."""
    claim = bot_claims.claim_comment(bot_claims.FIXER, "fix", NOW, ttl=bot_claims.PR_CLAIM_TTL)
    comments = [_c(claim, NOW)]
    assert bot_claims.occupied(comments, bot_claims.REBASER, ttl=bot_claims.PR_CLAIM_TTL) is not None

    done = bot_claims.done_comment(bot_claims.FIXER, NOW + dt.timedelta(minutes=20), "fixed")
    assert bot_claims.occupied(comments + [_c(done, NOW + dt.timedelta(minutes=20))],
                               bot_claims.REBASER, ttl=bot_claims.PR_CLAIM_TTL) is None


def test_a_claim_past_its_ttl_locks_nothing():
    """A crashed run must not freeze a subject forever."""
    old = NOW - dt.timedelta(hours=5)
    comments = [_c(bot_claims.claim_comment(bot_claims.FIXER, "fix", old, ttl=bot_claims.PR_CLAIM_TTL), old)]
    assert bot_claims.occupied(comments, bot_claims.REBASER, ttl=bot_claims.PR_CLAIM_TTL) is None


def test_an_implementer_that_opened_a_pr_still_holds_its_issue():
    """`pr-open`/`implemented` mark work that is NOT finished, so they hold the subject."""
    body = bot_claims.done_comment(bot_claims.IMPLEMENTER, NOW, "pr-open")
    assert bot_claims.occupied([_c(body, NOW)], bot_claims.REFINER) is not None
