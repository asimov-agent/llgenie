# Live-vs-tree drift: the comparison runbook for SOUL/skill issues and PRs

**Trigger (owner instruction 2026-10-30, #1104):** every ongoing issue and every docs PR whose
subject is — *or cites* — a `SOUL.md` or a skill must be checked against the bots' **live** host
profiles, and every gap is a finding that becomes a **new tracked issue**. Nothing here is assumed
true from the repo copy alone: `agents/<profile>/**` on `main` is the **versioned** copy, and
`~/.hermes/profiles/<profile>/**` is what each bot actually executes. A gap between the two is the
defect — not the versioned text, not the live text, the *gap*.

## When to run it

Run the full comparison when any of these is true:

- an issue or PR **touches** `agents/<profile>/**` (any SOUL or member skill),
- an issue or PR **cites** a SOUL/skill (states "per the lane's SOUL", "the skill says", a rule is
  quoted from either copy),
- you are reviewing *any* issue or PR about a bot's behaviour, even one that does not claim to edit
  the tree (the live profile may already describe behaviour the tree never saw).

Do not restrict the check to the lane the PR names: a SOUL/skill PR commonly has a *sibling* gap in
another lane (the lane whose rule a change borrows). Run the sweep repo-wide, then file per owning
lane.

## The two commands

```bash
make -s check-agent-profiles          # the gate: names the gap CLASSES (and reds CI on tree-only ones)
make sync-agent-profile PROFILE=<p> CHECK=1   # byte-compares ONE profile's tree copy against its live (exit 0 = identical)
```

Notes:

- `check-agent-profiles` classes are `live-longer`, `live-edited-not-tree`, `fleet-block-drift`.
  `fleet-block-drift` is tree-only (a versioned SOUL stopping a rule its manifest declares) and
  reds CI; `live-longer` and `live-edited-not-tree` need a live profile, so **CI never sees them** —
  they exist only on a host run. Running this on a fresh clone proves nothing about the first two.
- `sync-agent-profile PROFILE=<p> CHECK=1` is NOT a write in `CHECK=1` mode. Exit 0 means the pair
  is identical; a `differ` line names the first divergent file (then `git status --porcelain
  agents/<p>/` and a byte size on both copies show the full extent).
- Always re-read the profile's own skill bundle — for the lane's OWN member file the runbook is this
  file's sibling; a host's shared `skills/` store holds ~480 foreign skills that the tree versions
  only under each lane's own directory, so a copy/push must copy the lane's own bundle directory,
  never the live `skills/` root.

## Capture the delta (this is what the issue/PR body carries)

Every touched or cited SOUL/skill issue or PR must end its review with a **delta record** in the
body, one row per divergent (or verified-identical) pair:

| profile | file | class | tree bytes | live bytes | direction | owning lane |
|---|---|---|---|---|---|---|
| `llgenie-planner` | `skills/.../references/proving-bot-claims.md` | `live-edited-not-tree` | 4164 | 20853 | live newer (prefix-of) | planner (#1062) |
| `llgenie-pr-merge-conflict` | `skills/llgenie-pr-rebase/SKILL.md` | `live-longer` | 43084 | 44581 | live newer | rebase lane |

Columns mean:

- **class** — the `check-agent-profiles` class, or `differ` when only the byte-compare flags it.
- **direction** — judged **on content, per hunk, never copied blindly**: a tree copy that is a
  *prefix* of live → live is newer (re-take live→tree); a live file edited *after* the tree commit →
  the lane's behaviour outran the repo (commit it via an issue+PR under `agents/<profile>/`). A tree
  file that exists with no live counterpart is the third direction (tree-only; that is what a
  versioned-into-tree PR intentionally produces).
- **owning lane** — the lane whose live profile diverged; the issue goes to that lane.

A row that reads `identical` for every profile is a valid (and valuable) delta record: it is the
**proof** the reviewer re-read the live host rather than the repo copy.

## Route every gap to a NEW issue — never a comment

A gap is a change to tracked, versioned behaviour, and this repo's contract is issue → branch → PR
that closes it. A comment on the touched PR is not a trackable deliverable; a gap deserves the same
issue-first treatment as any measured defect:

1. `gh issue create` scoped to the **owning lane** (six sections: `## Problem` with the measured
   table, `## Why it matters`, `## How we fix it`, `## Benefit`, `## Acceptance criteria`, `##
   Technical`), and verify the body order by reading it back.
2. Link the new issue from the delta record (the row's owning-lane column names it).
3. The owning lane fixes it by issue+PR under `agents/<profile>/`. The **docs lane writes the fix
   only under explicit dispatch**, and the delegation is named in the PR body (e.g. #1062 to the
   planner, #885 to the rebase lane).
4. **Never run `sync-agent-profile` in write mode for a lane whose live is richer** — a write-mode
   sync copies repo→profile and would silently truncate the newer live with no gate noticing (#791).
   `CHECK=1` only, always.

## Acceptance for a SOUL/skill review

- [ ] `make -s check-agent-profiles` run at a measured head (quote the sha + clock beside it).
- [ ] `make sync-agent-profile PROFILE=<p> CHECK=1` run for each profile the issue/PR touches or
      cites, with the byte pair recorded.
- [ ] The issue/PR body carries the delta record table.
- [ ] Every gap row names its owning-lane issue (newly filed if none exists); nothing lives only in
      a comment.
- [ ] The touched profile's own tree copy is re-synced live→tree at the **final PR head** (not the
      cut point), so `CHECK=1` stays green on `main` after merge.
