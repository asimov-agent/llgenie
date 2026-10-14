# How the bots stay out of each other's way: claims on the issue

Related: issues #261 (the implementer reads the thread) and #263 (the refiner).

## The problem

Three bots work the same backlog. The refiner reviews issues, the implementer takes them, the
fix-bot repairs PRs. Nothing told them about each other, so the *schedule* had to be the race
protection — and any change to a cadence risked two bots on one issue.

## The rule

A bot that is going to refine or implement an issue **says so on the issue, before it starts**:

    <!-- bot-claim: refiner 2026-10-14T22:10:03Z refine -->
    <!-- bot-done:  refiner 2026-10-14T22:41:55Z refined -->

Any other bot reads the comments and stands down while the newest comment is RECENT and has not
been concluded by a `done` marker. It then takes the **next** issue in the list — it does not stand
down for the whole run.

## The kinds of `done`

`done` is not one thing, and the difference decides whether the next bot may take the issue:

| kind | means | effect |
|---|---|---|
| `refined` | the refiner restated the issue | releases it, for the implementer |
| `pr-open` | implemented, PR **awaiting approval** | **still occupies** — no second implementation |
| `merged` / `closed` | landed or rejected | releases it, resolved |
| `pr-open` with a failed fix-bot loop | still `pr-open` | the fix-bot owns the PR, not the issue |

## Why three hours

`CLAIM_TTL` is longer than the agent jobs are budgeted for (an hour), and short enough that a run
that crashed without posting `done` does not hold the backlog for a day. A stale claim locks
nothing.

## Where it lives

`scripts/bot_claims.py`, shipped **byte-identically** in the refiner's branch and the implementer's,
so whichever merges first makes the other a no-op. Tests: `tests/test_issue_refiner.py` and
`tests/test_issue_implementer.py` — including "claimed by the other bot → take the next issue",
"its own claim never blocks it", "a stale claim locks nothing", and "`pr-open` occupies while
`merged` releases".
