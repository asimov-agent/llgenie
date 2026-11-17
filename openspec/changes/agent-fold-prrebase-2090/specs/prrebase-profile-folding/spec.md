## ADDED Requirements

### Requirement: Every live rule of the pr-rebase lane is versioned in the tree
The tree copy `agents/llgenie-pr-merge-conflict/skills/llgenie-pr-rebase/` SHALL contain, byte for
byte, every line the live profile's `SKILL.md` carries — inside `SKILL.md` itself or verbatim in a
`references/` file the SKILL.md links — so a profile rebuild cannot drop a lane lesson (#791, #2090).

#### Scenario: zero-loss fold
- **Given** 32 live-only lines (17 pitfall bullets, a 15-line verdict/salvage block) measured at main `bb29cc9994`
- **When** the fold is committed and the containment check replays at the pushed head
- **Then** every one of those lines appears verbatim in the tree union of `SKILL.md` plus `references/`, and the containment command exits 0

#### Scenario: the cap is respected, not raised
- **Given** the live `SKILL.md` is 104,616 chars, over the skill writer's 100,000-char cap
- **When** `tests/test_agent_profiles.py` runs against the tree
- **Then** the tree `SKILL.md` is under the cap and no `skill-size` finding names this lane

### Requirement: The fold never writes the live side
The fold SHALL move live-only lines live→tree verbatim (append into `references/`, pointer lines in
`SKILL.md`) and SHALL NOT edit any file under `~/.hermes/profiles/llgenie-pr-merge-conflict/`. The
live SKILL.md staying over-cap is the documented overflow contract (#2084, #2118); reconciling the
live side is a separate work item (#2879).

#### Scenario: direction of the fold
- **Given** the lane's drift report `38 same / 1 drifted / 1 live-missing / 13 live-only`
- **When** the fold PR lands
- **Then** the tree gained the 32 lines and the live profile is byte-for-byte what it was before the change
