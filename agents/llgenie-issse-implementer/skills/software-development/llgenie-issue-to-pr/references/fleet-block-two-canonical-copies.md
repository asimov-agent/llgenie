# The fleet standing-rules block has TWO canonical copies — keep both in lockstep

Adding or editing a bullet in the standing-rules fleet block touches BOTH files, or the splice
idempotency test reds:

1. **`agents/standing-rules.md`** — the fleet rulebook the #873 gate compares each profile SOUL
   against (`fleet-block-drift`). Add the bullet here **and** mirror it verbatim into all 13
   `agents/<profile>/SOUL.md` (same position), else that gate reds a profile whose SOUL drifted.
2. **`agents/llgenie-pr-merge-conflict/skills/llgenie-pr-rebase/references/standing-rules.md`** —
   the fenced source `splice-fleet-block.py` reads (default `$REBASE_STANDING_RULES`).
   `tests/test_rebase_lane_scripts.py::test_the_fleet_splice_is_idempotent...` splices the
   pr-merge-conflict SOUL against THIS file and asserts a **no-op**. If the SOUL gained a bullet
   the skill reference lacks, the splice correctly reports
   `REFUSING: the rule source is older than this SOUL — it would drop 1 rule(s)` and the idempotent
   arm reds (rc!=0) — measured as the exact CI/local unit failure on the #1721 PR before the skill
   reference was updated.

The splice tool compares rule **signatures** (first 40 chars, emphasis/punctuation stripped), so a
bullet missing from the source = the whole rule looks "lost" from the SOUL's newer block. When you
see that REFUSING message, the direction is: the SOUL is NEWER than the splice source — update
`references/standing-rules.md` (and `agents/standing-rules.md` + every SOUL), never `--force` a
bypass. `--force` would ship a source that drops a current rule — the exact silent-revert the tool
exists to prevent.

Discipline: change the bullet in all three (canonical fleet rulebook + every SOUL + the splice
skill reference) before pushing, then run `tests/test_rebase_lane_scripts.py::test_the_fleet_splice...`
and `tests/test_agent_profiles.py` — both must pass on the same commit.
