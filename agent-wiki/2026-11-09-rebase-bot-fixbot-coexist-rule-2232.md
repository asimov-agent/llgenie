# Restating the rebase-bot's narrowed fix-bot coexist rule after #2078 (issue #2232)

#2078 (c8141343) narrowed `scripts/rebase_bot_sweep.py`'s fix-bot coexist rule: a red PR
**measured behind** whose only red is the staleness gate is taken by the rebase — the rebase is
the precondition for `check-pr-base`, so "fix-bot owns a red PR" cannot swallow a stale one
(issue #2071, half B). The decision keys on the measured-behind fact (`if behind is True:
return REBASE`, :134-136), never on the masked `mergeStateStatus` string, and the fix-bot
coexist fires only when `not measured_behind` (:392-394/:420). A PR red for a real failing test
stays the fix-bot's.

Two user-facing descriptions of the rule were not touched by #2078 and still asserted the
pre-#2078 ownership — `.github/workflows/rebase-bot.yml:22-24` ("a merely-BEHIND PR that is RED
is left to the fix-bot") and `docs/BOTS.md`'s rebase-bot section (issue-cited :891/:903-906,
current bullet at :939, "leaves a red, merely-behind PR to the fix-bot"). The stale text pointed
a lane at a fix-bot repair that could never clear a branch-lineage red — the exact deadlock
#2071 measured, where a stale-AND-red PR reported `BLOCKED` and the state-only read passed it
over.

Both sites now restate the narrowed rule in substance; the CONFLICTED-red-PR take clause is
preserved unchanged in each. Measured at `62c631b7` — `git log 7ffbb6f1..62c631b7 -- <both
files>` was empty.

#2232
