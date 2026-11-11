## MODIFIED Requirements

### Requirement: the rebase-at-worktree-start fleet rule teaches plain --force-with-lease for a rebase push

The canonical fleet rule `## Rebase at worktree start ##` and every copy of it (each lane's
`SOUL.md` rebase block, the pr-rebase splice source `references/standing-rules.md`, and every
per-lane `references/rebase-at-worktree-start.md`) SHALL teach the rebase push as plain
`--force-with-lease` after a fresh fetch — never `--force-if-includes` as an option — because a
rebased head does not contain the old remote tip and `--force-if-includes` would rightly refuse it
(the #1960-corrected force-push line). Where the remote tip IS an ancestor of the new head
(amend/integrate pushes), the #1960 line's own sanction of `--force-if-includes` stands untouched.

#### Scenario: no scoped file offers --force-if-includes for the rebase push
- **Given** the fleet rulebook at this change's head
- **When** `grep -r -- '--force-if-includes` after a fresh fetch'` is run over
  `agents/standing-rules.md`, `agents/*/SOUL.md`, the pr-rebase `references/standing-rules.md`, and
  every `agents/*/skills/**/references/rebase-at-worktree-start.md`
- **Then** the grep matches nothing

#### Scenario: every copy carries the corrected phrase byte-identically
- **Given** the 20 scoped files (canonical, 13 SOUL mirrors, splice source, 5 per-lane references)
- **When** the corrected phrase is compared across them
- **Then** the phrase reads `plain \`--force-with-lease\` after a fresh fetch (#1960: a rebased head does NOT contain the old remote tip, so \`--force-if-includes\` would rightly refuse it)` byte-identically in all 20, and no other rule text moves
