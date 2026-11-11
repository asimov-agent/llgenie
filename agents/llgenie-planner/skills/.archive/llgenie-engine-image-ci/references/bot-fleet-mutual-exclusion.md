# Multiple bots on one repo: mutual exclusion on BOTH axes

Moved out of SKILL.md (which hit its 100k character ceiling). Companion to the "Trigger guards
drift" and "A workflow a human can dispatch must state the work it will do" sections there, and to
`references/bot-fleet-audit.md` (the exercise→fix→merge loop) and `references/fleet-exercise.md`.


A fleet of autonomous bots (implementer, refiner, fix, rebase, reviewer) can all touch the same
issue or PR branch. Before assuming they cannot race, audit each bot on TWO independent axes:

- **(a) does it post a claim BEFORE its first mutation?** and
- **(b) does its picker read ALL sibling bots' claims?**

Run (a) and (b) separately for every bot — a bot that claims after picking, or claims but whose
own picker ignores claims, still duplicates itself. Do NOT trust a docstring or commit message
that says a bot "never picks an issue another has claimed": that is a claim about a MECHANISM,
and the mechanism is often label-based while the the guard-bot only posts a COMMENT that no
picker reads. Verify by mechanism, not by prose: `git show <ref>:scripts/<bot>.py | grep 'issue.*comment'`
for (a) and `| grep 'claim\|label\|skip'` in its picker for (b).

Three concrete traps measured when auditing this fleet:

- **A label-based skip is not a lock if the claiming bot never sets the label.** The implementer
  claims with a comment only; the refiner skips by label. So a "claimed" issue is still pickable —
  the docstring about not racing is false. Labels are the human-facing state; a comment is the
  machine-facing lock, and the two must coexist, not substitute.
- **An attempt counter derived from post-success commits hides an in-flight run.** counting
  `fix(bot):` commits works only after a repair lands; a repair running up to minutes with no
  commit yet is invisible to the next sweep, which dispatches a second agent on the same branch.
  Guard the pick against an in-progress claim, not a completed commit.
- **A claim with no expiry freezes a subject for ever.** A claim from a run that died (cancelled,
  out of budget, runner lost) lives forever as a comment/label. A shared protocol needs a
  staleness rule: a claim older than the longest job budget is reported as stale and does NOT
  block, so a dead run is visible instead of silently freezing the issue.
- **The TTL a claim ANNOUNCES is decoration — the reader's TTL decides.**
  `claim_comment(..., ttl=...)` only shapes the human-facing sentence; each
  reader ages a claim by its OWN TTL, so the "leave it for 4 hours" a maintainer
  reads and the rule the bots apply can disagree (verified: `bot_claims.py`
  passes `ttl` only into the prose). Keep read and write on one value — store the
  expiry in the marker, or make the writer's announced TTL the only number every
  reader consults.
- **A claimed subject is released only by the LAST step's `done` — a cancelled
  run keeps the claim.** Cancellation (human, the push-supersede rule,
  `timeout-minutes`) skips every step after the cancel point, so the claim stays
  and the PR freezes for the whole TTL. When auditing a fleet, verify by grep:
  are there `if: cancelled()` cleanup steps, or is release only in the last step
  (which never runs when cancelled)? A workflow with `cancel-in-progress: false`
  and no `cancelled()` cleanup leaks a claim on every cancelled run.

The right shape is ONE shared module (`scripts/bot_claims.py`): a single machine-readable marker
`<!-- bot-claim:{bot}:{kind}#{n} @ {iso} -->`, `claim()` posted before the first mutation,
`claims()`/`blocked_by()` consulted by every picker, `release()` recording the outcome, and a stale
expiry. Add a table-driven test enumerating the bots so a new bot that neither claims nor consults
claims fails CI — a convention without a guard drifts, and each bot inventing its own marker string
is the failure shape.

Two more fleet rules earned in the first real merge sequence:

- **A claim's outcome is a 'done' comment, and it has only two kinds.** A claim is 'concluded' only
  when a bot posts a done comment whose verdict is one of: the issue was refined, or the work is
  implemented (either a PR open but unapproved, or closed-and-merged). A bot skips an issue whose
  latest comment is RECENT and not concluded by a done comment — and it moves to the NEXT issue, it
  does not stop. 'Done' releasing the lock is what lets work exist in its intended form rather than
  merely because a bot started.
- **Schedules must not manufacture the one collision the claim cannot undo.** Two workflows sharing
  a cron minute race at the START: both have read the thread before either has commented, so the
  claim comment cannot sort it out after the fact. Put every scheduled bot on a fixed minute grid
  (11/31/51, ~20 min apart) so no two begin together, give EVERY scheduled workflow a concurrency
  group (a run that outlives its interval otherwise overlaps its own next tick), and pin both with a
  test (`tests/test_bot_schedule_gaps.py`): no two scheduled workflows share a minute, working jobs
  sit on the grid, and every scheduled job has a group. A read-only reporter may sit off the grid
  but still may not share a minute with a working job.

- **A guard that bounds a set must DERIVE that set, or it cannot see the members added after it
  shipped.** A green-but-blind guard is the worst kind: it enforces the rule over a HARD-CODED
  enumeration of the very thing the rule governs, so the object of the rule that arrives later is
  silently outside its reach. Measured: the slot-uniqueness guard carried a hand-written tuple of six
  workflow filenames; three scheduled bots merged afterwards (rebase, refiner, code-review) were
  never in it, and the collision the guard exists to catch began firing while the guard stayed green
  (``issue-bot 23 6 * * *`` and ``rebase-bot 23 */6 * * *`` both at 06:23 UTC). Fix: derive the scope
  from the SYSTEM — every ``.github/workflows/*.yml`` with a ``schedule:`` block is a scheduled bot,
  and the always-firing hourly/6-hourly crons reserve their minute the same way a fixed slot does
  (they own it on the hours they fire) — with NO literal list. Then add a regression test that PINS
  the derivation (the derived set must equal what the filesystem yields), so re-introducing a
  narrowed literals list — the exact step that caused the blind spot — fails the suite. This is the
  complement to "prove the guard fires": proving it FIREs is useless if its scope never CONTAINS
  the newcomer.
