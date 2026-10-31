# The live-vs-tree comparison runbook for SOUL/skill work (#1104)

## What changed

The owner's 2026-10-30 comparison duty — compare `agents/<profile>/**` against the bots' live host
profiles on every SOUL/skill issue or PR, and file a **new issue** for every gap — was already a
measured SOUL duty (the `host-vs-repo gap is a finding` bullet), but it had no repeatable procedure.
This change makes it one:

- **New runbook** `agents/llgenie-documentation-maintainer/skills/llgenie-docs-maintainer/references/live-vs-tree-drift.md` —
  the triggers, the two commands, the delta-record table, the direction rules, and the routing:
  - triggers: an issue/PR **touches** or **cites** a SOUL/skill (never restrict to the named lane);
  - commands: `make -s check-agent-profiles` + `make sync-agent-profile PROFILE=<p> CHECK=1`;
  - delta record: a table (profile, file, class, tree bytes / live bytes, direction, owning lane)
    that every such issue/PR body must carry — `identical`" rows included, as the proof the live host
    was re-read and not the repo copy;
  - direction judged **on content, per hunk**: prefix-of → live newer (re-take live→tree); live edited
    after the tree commit → issue+PR; never write-sync a richer live («CHECK=1 only»);
  - every gap → a **NEW issue** scoped to the owning lane, **never a comment**; the docs lane writes the
    fix only under explicit dispatch, named in the PR body.
- **SKILL.md** "Host behaviour vs the versioned tree" section now points at the runbook and tightens
  the routing bullet (delta recorded in the issue/PR body; a comment-only gap is not trackable).

Same PR, the docs lane folded its own live→tree drift so `sync-agent-profile CHECK=1` stays green on
`main` after merge:

- `SKILL.md` **v1.0.13 → v1.0.15** (v1.0.14 carried the local-fold-during-in-flight and the
  cancellations-are-three-classes lessons; v1.0.15 added the runbook pointer);
- `references/ci-triage-for-docs-prs.md` **8,683 → 11,115 b** (the "short cancel at a superseded head
  (a third class)" section).

## Acceptance

- [ ] `make -s check-agent-profiles` clean at the PR head.
- [ ] `make sync-agent-profile PROFILE=llgenie-documentation-maintainer CHECK=1` → 6 files byte-identical.
- [ ] routed gaps: every SOUL/skill review carries the delta record and names an owning-lane issue.
