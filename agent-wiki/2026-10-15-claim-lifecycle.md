# A claim now carries its own terms, and a dead run releases it (#291, #292)

## Why

The claim protocol (#279/#285) made every bot announce the subject it is about to mutate with a marker
another bot reads. Two properties of it were decoration rather than mechanism:

- **The marker carried no TTL** (#292), so the READER decided how long a claim held. A rebase that
  asked for 30 minutes blocked a 4-hour reader, and the sentence a maintainer read ("leave it alone
  for the next 4 hours") disagreed with what the bots did. The writer's `ttl` only shaped the prose,
  and any window under two hours was announced as "1 hour".
- **The marker carried no run** (#291), so a holder that died — cancelled by the next push (#289), by
  hand, or by `timeout-minutes` — kept the lock for the whole TTL: the release lives in the run's LAST
  step, and a cancelled job skips every remaining step. The sibling that skipped the subject said so
  only in a log line.

## What landed

```
<!-- bot-claim: fix-bot 2026-10-15T05:20:01Z fix ttl=240m run=38761102690 -->
```

- `occupied()` ages a claim by **the TTL its own marker announced**; the caller's value is the fallback
  for a marker written before the field existed (covered by a legacy-marker test).
- `run_is_live(gh_call, run_id)` reads `gh run view <id> --json status,conclusion` through the caller's
  own gh runner (the module still shells out to nothing). `completed` → the claim is over, so the
  subject is free NOW; a queued/in-progress run still holds; **an unreadable answer is `None` and never
  releases** — "we could not check" is not "it is gone".
- `released()` is the loud half: it names the holder and why it no longer holds ("its run 424242 is no
  longer running", "the claim announced 30 minutes and that has passed"), and all four pickers print it
  when they take a subject that had a claim. The skip is never silent again.
- Every writer passes its own `ttl` and `GITHUB_RUN_ID`; `cancelled` joins the release words so a run
  that stops without finishing can say so explicitly.
- **Deliberately no `if: cancelled()` workflow step**: a cancellation cleanup runs best-effort after
  the cancellation is already requested, while the liveness check works even when the runner
  disappears without a last word.

## Verification

- `tests/test_bot_claims.py` + the four bot suites: **85 passed** in `llgenie/test:latest`.
- **Falsified first**: the new protocol tests against the pre-fix `scripts/bot_claims.py` give
  **8 failed, 6 passed** (the marker terms, the announced-TTL rule, the legacy fallback, the dead-run
  release, the loud takeover, the release vocabulary).
- `tests/test_issue_refiner.py` asserted the parsed claim shape exactly; updated to the new
  `{bot, at, work, ttl, run}`.

## Still open

- #293 / #294 / #296 — the reviewer bot's blind spots and the queued-run alarm's delivery.
- #295 — the trigger guard audit (queued-alarm has none; four accept any collaborator level).
