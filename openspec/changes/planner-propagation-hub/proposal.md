# planner-propagation-hub — proposal

Issue: [#1194](https://github.com/asimov-agent/llgenie/issues/1194)

## Why

Issue #1194 states that the planner must be the propagation hub: the moment a lane's finish lands (or a PR
reaches a fresh head or merges), the planner routes the dependent lanes (tester, security, architect, reviewer)
onto the same PR in the same pass, on-record, instead of leaving them to discover the new head by polling. A
PR can otherwise sit for a pass with nobody told to look.

Measured against the versioned planner profile — `agents/llgenie-planner/SOUL.md` and
`agents/llgenie-planner/skills/llgenie-bot-orchestration/SKILL.md` — that propagation-hub rule is **absent**.
The closest statement, the SKILL's "A merge is a dispatch trigger", routes only the rebase lane
(`llgenie-pr-merge-conflict`) on a merge-to-main; it does not route the dependent review lanes
(tester/security/architect/reviewer) onto a fresh-head PR in the same pass. Nothing in the profile states that
a lane finish must trigger a same-pass on-record routing of dependents. So #1194 is not a no-op: the rule text
must be added to the versioned planner profile and PR'd.

## What Changes

- Add one section to `agents/llgenie-planner/skills/llgenie-bot-orchestration/SKILL.md`, mirroring the issue's
  three numbered points (read the finish as evidence; post the routing comment naming the dependent lanes;
  dispatch each named lane via `message_agent`/the board, or say why it was not dispatched) and the
  on-record / no-re-dispatch disposition. In the profile's own voice, no claim that the runtime already does it.
- No new planner vehicle, no edits to other lanes' profiles, no code.

## Benefit

The propagation-hub rule is versioned under `agents/llgenie-planner/` so the active planner can be given the
same instruction and be diffed/synced like every other profile rule (issue #791). Issue #1194 gets an
implementing PR.

## Not covered

- Other lanes' profiles (out of scope by dispatch).
- A runtime enforcement gate — this change version the rule text only.

## Technical

- `agents/llgenie-planner/skills/llgenie-bot-orchestration/SKILL.md`: one new section in the planner's own
  voice with no other lane's profile touched.
- `docs/changes.d/planner-propagation-hub.md` + `agent-wiki/2026-10-31-planner-propagation-hub.md`,
  reference #1194.
- Gates: `make lane-preflight` (fast gates), `make openspec-validate NAME=planner-propagation-hub`,
  `make check-agent-profiles`, scoped `ci-unit` gates.
