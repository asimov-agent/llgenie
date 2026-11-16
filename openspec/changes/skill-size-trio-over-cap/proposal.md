# Change: skill-size-trio-over-cap

<!-- Why -->

## Why

The `skill-size` gate (`SKILL_MAX_CHARS = 100_000` in `scripts/check_agent_profiles.py`, issue #2084) is ON but runs on a dated exemption record (`tests/fixtures/skill-size-exceptions.json`) because three tree `SKILL.md` bodies still sit past the cap. `skill_manage` refuses every patch to an over-limit body and rolls the whole batch back, so those lanes' tree copies cannot take corrections, and a tree→live sync could push an un-patchable body into a live profile.

Measured at `origin/main` `58db552b7` (fetched this session), the trio the record actually carries is:

```
agents/llgenie-engine-improver/skills/llgenie-engine-improver/SKILL.md      106,390 chars  +6,390
agents/llgenie-pr-merge-conflict/skills/llgenie-pr-rebase/SKILL.md          104,616 chars  +4,616
agents/llgenie-planner/skills/llgenie-bot-orchestration/SKILL.md            102,325 chars  +2,325
```

The issue body (#2114) names `llgenie-pipeline-maintenance` (103,203 at `c3f3b2ac`) — that file has since been slimmed (96,513 now, no exemption entry) and `llgenie-bot-orchestration` was added to the record on 2026-11-11 by the #2262 planner fold. The issue body is corrected to this measured trio as part of this change.

## What Changes

- For each of the three files, follow the #2084 method: take the TREE copy as the base, move the largest self-contained sections VERBATIM into `references/<topic>.md`, and link every new reference from the always-on body:
  - engine-improver: `## Working a test/CI refactor in this tree` (46,573 chars) → `references/test-ci-refactor-method.md`
  - pr-rebase: `## Fleet orchestration (issue #1010) — this skill's lane side` (19,138 chars) → `references/fleet-lane-side.md`
  - planner: `## Interrogating a filter: every subcommand must agree` + `## A filter, its twin and the classifier are one set` (8,038 chars) → `references/filters-and-classifiers.md`
- Prove zero loss per file the #2084 way: the pre-change distinct-line set must be a subset of the slim body plus the new references — `LOST: 0` before the commit.
- Delete all three entries from `tests/fixtures/skill-size-exceptions.json` in the same change (the gate reds a stale exemption; an empty `files` map is the ordinary no-exemption state).
- Update the #2114 issue body to the measured trio (the issue, the OpenSpec change, and the code must not contradict each other).
- The PR body states a `SYNC: <profile> make sync-agent-profile PROFILE=<profile>` line for each of the three profiles (issue #1724), so the merged slimmed trees are propagated live after landing.

## Impact

- Affected specs: `agent-profiles` (MODIFIED — the size gate runs with no exemptions in play)
- Affected code: three `agents/<profile>/skills/*/SKILL.md` bodies, three new `references/` files, `tests/fixtures/skill-size-exceptions.json`
- No live-profile copy is written from a tree copy as proof; `sync-agent-profile CHECK=1` is not the proof (#928/#1079).
