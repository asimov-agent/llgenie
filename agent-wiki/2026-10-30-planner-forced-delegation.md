# Planner forced-delegation rule landed in the tree (issue #1030, 2026-10-30)

The implementer lands the planner lane's owner-directed rule into `agents/` (the #919 tree vehicle), per the
planner's delegation authorized under #1030.

- **`agents/llgenie-planner/SOUL.md`** gains the clause verbatim: **"Never let 'holding' cover idleness."** A
  lane parked on a real gate (a producer's direct word, an un-merged base) is parked; a lane that could be doing
  independent, unassigned, gate-free work is idle-capable and must be **forced** onto it. On every pass, beyond
  "which lanes are busy", answer "which lane is idle-capable RIGHT NOW": an open, unassigned issue it can complete
  without the blocked gate exists → dispatch it, out loud, with a `BOT <name> · #<id> · …` command. "This waits on
  the gate" stops being an excuse for "so I do nothing" the moment there is an issue that doesn't (owner 2026-10-30).
- **`agents/llgenie-planner/skills/llgenie-bot-orchestration/references/forced-delegation.md`** (23 lines) is the
  runnable behaviour — the three re-fits (engine → #974/#990, reviewer → #976/#988, architect → #973) and the
  fit-selection rules — committed from the planner's live profile (authorized re-take).

Verification: all eight `_stated_block == fleet_block()` stay TRUE, the planner's duplicate-report row is the
retained content paragraph only, gates `lint`/`check-docs`/`check-wiring`/`changes-index` all 0. Referenced:
`agents/llgenie-planner/SOUL.md`, `agents/llgenie-planner/skills/llgenie-bot-orchestration/references/forced-delegation.md`,
issue #1030.
