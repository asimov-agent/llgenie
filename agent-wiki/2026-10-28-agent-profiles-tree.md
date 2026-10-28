# A host agent's SOUL and skills live in this repo

**Issue:** [#791](https://github.com/asimov-agent/llgenie/issues/791) · **OpenSpec change:**
`agent-profile-tree` · **PR:** [#834](https://github.com/asimov-agent/llgenie/pull/834)

## What was verified against the spec

The two host agents — `llgenie-planner` (the orchestrator) and `llgenie-issse-implementer` (the
implementer, triple `s`) — kept `SOUL.md` plus `skills/` in `~/.hermes/profiles/<profile>/`, outside
version control. Measured on `main@17cdcf3`: `git log --all --oneline -- '*SOUL*'` returns nothing and
`agents/` does not exist, while `gh api repos/asimov-agent/llgenie/contents/agents` is a 404. The bot
legs were the opposite: `.hermes/skills/` holds their contracts and `make check-agent-skills` gates
them (issue #577). So the instruction a credential-holding agent runs under was the one change here
nobody could diff.

`agents/` is that behaviour's home now, one directory per profile, mirroring the layout Hermes loads:

```
agents/manifest.json
agents/llgenie-planner/SOUL.md
agents/llgenie-planner/skills/llgenie-bot-orchestration/SKILL.md
agents/llgenie-planner/skills/llgenie-bot-orchestration/references/proving-bot-claims.md
agents/llgenie-issse-implementer/SOUL.md
```

The tree carries what the live profiles held when this PR opened (SOUL.md 5,149 b / 336 b). The
orchestrator's skill is the one file that moves while its own agent is working: it grew from
17,589 b to 19,215 b during this change (a kanban dispatch recipe and two claim-reading pitfalls),
so the tree carries the later text and `CHECK=1` was re-run against it. The repository becomes the
source of truth when this merges: from then on a change to a host agent's behaviour is a PR, and
`make sync-agent-profile` is the only way the profile moves.

### Host-only proof (recorded here because CI has no profiles)

Run on the owner's host against the LIVE profiles, from the change's worktree:

```
$ make sync-agent-profile PROFILE=llgenie-planner CHECK=1
[agent-profile] llgenie-planner: destination /home/asimov/.hermes/profiles/llgenie-planner (from default (~/.hermes/profiles/<profile>))
[agent-profile] OK: 3 file(s) of agents/llgenie-planner match /home/asimov/.hermes/profiles/llgenie-planner byte for byte

$ make sync-agent-profile PROFILE=llgenie-issse-implementer CHECK=1
[agent-profile] llgenie-issse-implementer: destination /home/asimov/.hermes/profiles/llgenie-issse-implementer (from default (~/.hermes/profiles/<profile>))
[agent-profile] OK: 1 file(s) of agents/llgenie-issse-implementer match /home/asimov/.hermes/profiles/llgenie-issse-implementer byte for byte
```

Both exit 0, so the tree IS what the two profiles run, byte for byte. The hermetic half of the same
claim runs in `make test-unit` against a temporary `HERMES_PROFILE_HOME`.

## Decisions

- **The manifest declares which standing rules a profile's SOUL must state.** The orchestrator
  declares `never-implement` + `never-merge`; the implementer's own 336-byte `SOUL.md` states
  neither (its "never merge" duty reaches it through `AGENTS.md` and the kanban protocol), so
  claiming otherwise would be a fiction the gate then "proved". A manifest that declares
  `never-merge` for **no** profile is itself a failure, so the rule cannot be emptied out quietly.
- **The gate reads the skill's `references/`.** The orchestrator skill names
  `references/proving-bot-claims.md`; committing `SKILL.md` alone would have shipped a rule pointing
  at a file the profile does not have. `skill-reference-missing` is a finding, and the file is in the
  tree.
- **The sync never deletes.** It writes only the files the tree carries, so a live profile's other
  skills, memory, `state.db` and `.env` are untouched: a sync that removed a skill would be a
  behaviour change nobody reviewed. A file the tree *should not* carry (`state.db`, `sessions/`,
  `memories/`, `logs/`, `.env`) is a `forbidden-path` finding in the gate instead.
- **The frontmatter reader is shared** with `scripts/check_agent_skills.py` — one definition of
  "frontmatter" for a skill, whichever tree it lives in.

## Status

- `make check-agent-profiles` — green on the committed tree; every rejection rule has its own test
  in `tests/test_agent_profiles.py` (19 cases, `# Given / # When / # Then` markers).
- `make sync-agent-profile … CHECK=1` — green against both live profiles (above).
- `make check-docs`, `make check-wiring`, `make check-agent-skills`, `make openspec-validate
  NAME=agent-profile-tree`, `make test-unit` — the PR's gate output.

## The planner's live SOUL and skill were folded back in (issue #851)

The tree was cut at 22:20Z, and the orchestrator's own `SOUL.md` and
`llgenie-bot-orchestration` skill kept being written after it: at `ed892cf6` the committed planner
SOUL was 5,149 b against 7,509 b live (the five standing rules — assignment-and-state reporting, a
report-is-a-claim, `cancelled` is not a verdict, one vehicle per issue, never push to a branch you
were not dispatched for), and the committed skill was one reference out of ten. The tree is only
a source of truth if it carries what the agent actually runs under, so #851 folds the live text in
verbatim on the same branch and PR (#903), extending the tree rather than opening a second vehicle.

- `agents/llgenie-planner/SOUL.md` — 7,509 b, `diff` against the live profile file is empty.
- `agents/llgenie-planner/skills/llgenie-bot-orchestration/` — `SKILL.md` 100,343 b plus all 10
  `references/*.md`; `diff -r` against the live skill directory is empty.
- `agents/manifest.json` unchanged: it declares `{name, rules}` for this tree, and
  `make check-agent-profiles` is the gate that reads it (a `path · sha256 · authored` row belongs to
  the superseded #834 schema, which this branch does not carry).
- Snapshot 2026-10-28T22:28:24Z. The live profile is written by its own agent while the sync runs, so
  the copy was taken twice inside two minutes: the first (22:27:37Z) carried 12 references, the second
  (22:28:24Z, the committed one) carries 10 — the orchestrator had just consolidated
  `agent-profile-sync-safety.md` and `ci-log-and-state-forensics.md` into
  `assertions-and-gates.md` (5,071 → 6,409 b) and grown `ci-state-and-queue.md`
  (17,005 → 17,821 b). The two superseded files were removed rather than left behind, because a tree
  that carries a reference the profile no longer has is the same defect in the other direction.
  The committed text is the second snapshot; drift after it is a new private edit that needs its own
  issue, not a silent second copy. This is the one place the sync cannot self-heal: the profile is a
  moving target while its own agent works, so a reviewer who re-runs the diff an hour later may see
  newer live text.

Gate output on that snapshot: `make check-agent-profiles` OK (2 profiles), `make check-agent-skills`
OK (10 legs, 11 skills), `make check-docs` OK (242 targets), `make lint` OK,
`make sync-agent-profile PROFILE=llgenie-planner CHECK=1` OK on all 12 committed files (SOUL.md,
`SKILL.md`, 10 references).
