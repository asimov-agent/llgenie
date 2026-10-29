# Arm auto-merge when the work is done (owner directive 2026-10-29)

The implementer lane's versioning of the owner directive — "their skill behavior should always be to set
the PRs to automerge when they are done with the issue/pr work" — through the #791 process on
`feat/agent-profile-implementer-skill`.

- **SOUL** already stated it: the creation-time arm from #912, and the fleet block's "Arm auto-merge when the
  work is done, not when it is approved" from #965.
- **Skill** (`references/queue-and-pr-mechanics.md`) now carries the operative half: arm at the last push /
  last check; read `autoMergeRequest` back in the SAME comment and report the arm time (`gh pr merge --auto`
  exits 0 and arms NOTHING on a non-default base, issue #964); the ONLY accepted reason a finished PR sits
  unarmed is an owner "do not merge" → `auto=none (owner instruction)` plus where the instruction lives; a
  stacked PR (base != main) cannot be armed and is reported as such rather than misreported as armed.
- **Tests** pin the operative half; negative control run (drop the section → 1 failed, restore → 64 passed).

Bookend for the pass: base `7db4ac99` (fetched), started `618591a7`, finished `3f517dc8`, local==remote==PR
head, `autoMergeRequest` read back `enabled=true`.

Referenced: `agents/llgenie-issse-implementer/SOUL.md`,
`agents/llgenie-issse-implementer/skills/containerized-repo-verification/references/queue-and-pr-mechanics.md`,
`tests/test_agent_profiles.py`.
