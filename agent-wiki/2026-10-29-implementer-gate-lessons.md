# Implementer gate lessons (2026-10-29): retired-bullet debt, one canonical, `--onto` stacked rebase

Three skill/gate lessons versioned onto `feat/agent-profile-implementer-skill` (#919) this session, each
pinned by a test with a negative control.

- **Retired arming bullet is gate-named debt.** `Arm auto-merge at PR creation` is neither a canonical title
  nor (appearing once) a duplicate, so the old gate saw nothing while two lanes ran under a contradiction of
  rule 16. `_retired_rule_debts` names every such SOUL in `report()` and as a `check` note — the same
  visible-not-silent contract as the duplicate-rule debt; removal is a protected SOUL write (`#1006`/`#1008`).
- **The fleet block has ONE canonical — `agents/standing-rules.md`, never the issue fence.** `fleet_block()`
  reads rule 16 as "Arm auto-merge when the work is done, not when it is approved"; issue `#873`'s body states
  it as "Arm when done, and only on a base of main" — same intent, different wording, and `_stated_block()`
  compares byte-for-byte against `standing-rules.md` only. Measured: the doc lane's live 13,394 matched the
  `#873` wording, so the planner's "take 13,394, block True" was measured against the wrong canonical and
  withdrawn. Tracked on **#1005** (the single surviving vehicle; #1009 closed as a duplicate of it). The doc
  SOUL's `_stated_block == fleet_block()` is now a durable regression.
- **`git rebase --onto` needs the three-argument form for a stacked child.** Using the branch's own remote
  tip as `<upstream>` gives an empty range and silently MOVES the branch to the new tip, dropping the child
  commit. The right form is `--onto <new-parent-tip> <old-parent-tip>`; recover with `git reset --hard <sha>`
  (the commit still exists), and verify `git merge-base --is-ancestor origin/<parent> HEAD` before a force-push.

Referenced: `scripts/check_agent_profiles.py` (`_retired_rule_debts`),
`agents/llgenie-issse-implementer/skills/containerized-repo-verification/references/{agent-profile-tree.md,queue-and-pr-mechanics.md}`,
`tests/test_agent_profiles.py`. Board: `#919` `MERGEABLE/BLOCKED` armed, only the inherited author-gate red.
