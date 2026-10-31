# The planner is the propagation hub (issue #1194, 2026-10-31)

Issue #1194 asks that the planner be the propagation hub — a lane finish or a merge routes the dependent lanes
(tester, security, architect, reviewer) onto the same PR in the same pass, on-record, ending the pass with
nobody untriggered.

First measurement: the rule was **absent** from the versioned planner profile. `agents/llgenie-planner/SOUL.md`
and `agents/llgenie-planner/skills/llgenie-bot-orchestration/SKILL.md` carry no statement of the hub behaviour.
`SKILL.md`'s "A merge is a dispatch trigger" routes only the rebase lane (`llgenie-pr-merge-conflict`); nothing
routes the dependent review lanes onto a fresh-head PR same-pass. So #1194 was not a no-op.

The change adds one section, **"The planner is the propagation hub"**, to
`agents/llgenie-planner/skills/llgenie-bot-orchestration/SKILL.md`, mirroring the issue's three numbered points
and the on-record / no-re-dispatch disposition, in the planner's own voice. No other lane's profile, no code.

Verification: `make openspec-validate NAME=planner-propagation-hub` exits 0, `make check-agent-profiles` green,
`make lane-preflight` passes, and the scoped `ci-unit` gates are green. Referenced: issue #1194.
