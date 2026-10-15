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


def test_the_marker_carries_the_ttl_the_reader_must_apply():
    """#292: the writer's own number binds. Before, the reader applied its OWN ttl and the sentence
    a maintainer read could disagree with what the bots actually did."""
    body = bot_claims.claim_comment(bot_claims.FIXER, "fix", NOW, ttl=dt.timedelta(minutes=30))
    assert "ttl=30m" in body and "30 minutes" in body, body
    assert bot_claims.claims([_c(body, NOW)])[0]["ttl"] == dt.timedelta(minutes=30)


def test_a_short_claim_does_not_block_a_reader_that_would_age_it_for_hours():
    """The #292 regression: a 30-minute claim must NOT hold for the 4 hours a PR reader passes."""
    old = NOW - dt.timedelta(minutes=90)
    body = bot_claims.claim_comment(bot_claims.REBASER, "rebase", old, ttl=dt.timedelta(minutes=30))
    comments = [_c(body, old)]
    assert bot_claims.occupied(comments, bot_claims.FIXER, ttl=bot_claims.PR_CLAIM_TTL) is None
    assert "30 minutes" in (bot_claims.released(comments, bot_claims.FIXER,
                                                ttl=bot_claims.PR_CLAIM_TTL) or "")


def test_a_legacy_marker_falls_back_to_the_readers_ttl():
    """A claim written before #292 carries no ttl: the reader's own value is the only fact there."""
    at = dt.datetime(2026, 10, 14, 11, 30, tzinfo=dt.timezone.utc)
    legacy = "<!-- bot-claim: fix-bot 2026-10-14T11:30:00Z fix -->\nleave it"
    now = at + dt.timedelta(hours=1)
    comments = [_c(legacy, at)]
    assert bot_claims.claims(comments)[0]["ttl"] is None
    assert bot_claims.claims(comments)[0]["run"] is None
    assert bot_claims.occupied(comments, bot_claims.REBASER, now,
                               ttl=bot_claims.PR_CLAIM_TTL) is not None
    assert bot_claims.occupied(comments, bot_claims.REBASER, now,
                               ttl=dt.timedelta(minutes=30)) is None


def test_a_cancelled_run_releases_its_claim_and_says_so():
    """#291: the claim names its run, and a reader that can ask releases it the moment it is over."""
    run_id = 424242
    body = bot_claims.claim_comment(bot_claims.FIXER, "fix", NOW, ttl=bot_claims.PR_CLAIM_TTL,
                                    run_id=run_id)
    assert f"run={run_id}" in body, body
    comments = [_c(body, NOW)]

    # Given the holding run is over -> the subject is free NOW, and the reason names the run
    dead = lambda rid: False                                            # noqa: E731
    assert bot_claims.occupied(comments, bot_claims.REBASER, ttl=bot_claims.PR_CLAIM_TTL,
                               is_live=dead) is None
    said = bot_claims.released(comments, bot_claims.REBASER, ttl=bot_claims.PR_CLAIM_TTL,
                               is_live=dead)
    assert said and f"run {run_id} is no longer running" in said, said

    # ...and a run still going holds it, with nothing to announce
    assert bot_claims.occupied(comments, bot_claims.REBASER, ttl=bot_claims.PR_CLAIM_TTL,
                               is_live=lambda rid: True) is not None
    assert bot_claims.released(comments, bot_claims.REBASER, ttl=bot_claims.PR_CLAIM_TTL,
                               is_live=lambda rid: True) is None


def test_an_unknown_run_state_never_releases_a_claim():
    """'We could not check' is not 'it is gone': a failed probe must not hand the subject over."""
    body = bot_claims.claim_comment(bot_claims.FIXER, "fix", NOW, run_id=1)
    comments = [_c(body, NOW)]
    assert bot_claims.occupied(comments, bot_claims.REBASER, is_live=lambda rid: None) is not None
    assert bot_claims.occupied(comments, bot_claims.REBASER) is not None, "no probe: ttl decides"


def test_a_concluded_subject_announces_nothing():
    """A `done` release is normal, not news: released() is only for a holder that DISAPPEARED."""
    body = bot_claims.done_comment(bot_claims.FIXER, NOW, "repaired")
    assert bot_claims.released([_c(body, NOW)], bot_claims.REBASER) is None


def test_run_is_live_reads_the_run_status():
    seen = []

    def call(args):
        seen.append(args)
        return '{"status": "in_progress"}'

    assert bot_claims.run_is_live(call, 5) is True
    assert seen[0][:2] == ["run", "view"] and "--json" in seen[0]
    assert bot_claims.run_is_live(lambda a: '{"status": "completed"}', 5) is False
    assert bot_claims.run_is_live(lambda a: '{"status": "weird"}', 5) is None
    assert bot_claims.run_is_live(lambda a: "not json", 5) is None
    assert bot_claims.run_is_live(lambda a: "", 5) is None

    def boom(args):
        raise RuntimeError("gh failed")

    assert bot_claims.run_is_live(boom, 5) is None


def test_cancelled_is_a_release_word():
    """A run that stops without finishing can say so, instead of only the TTL releasing it."""
    assert "cancelled" in bot_claims.DONE_RELEASES
    body = bot_claims.done_comment(bot_claims.FIXER, NOW, "cancelled")
    assert bot_claims.occupied([_c(body, NOW)], bot_claims.REBASER) is None
