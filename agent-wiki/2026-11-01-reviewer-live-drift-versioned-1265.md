# Reviewer lane: live-only drift versioned into the tree

Issue: #1265. Related: #791, #1062, #1156.

The reviewer lane's live profile accumulated lessons the tree lacked — a versioning-PR violation under the recurring-drift tracker (#1156). Measured at live/main `1db367a2` (API + `refs/remotes/live/main` both `1db367a2`):

- `SOUL.md` — live 11,887 b vs tree 11,802 b. Tree lacks the reporting line appended to "When a change is wrong, the output is a comment naming the file, the line and the exact fix.": **Message `@llgenie-planner` with the PR number, the sha, the run id, and the verdict.**
- `SKILL.md` — live 49,745 b vs tree 47,436 b. Tree lacks four live-only accretions:
  - `## Role artifact (2026-11-01)` — "the artifact is the review comment: file, line, verdict, sha, and run id. Do not write the fix."
  - the detached-worktree baseline note ("`git stash` is a no-op on committed work so the base needs a detached worktree")
  - the one-settlement / one-acknowledgement lesson
  - the reload-direction section (which references `live-profile-reload.md`)
- `references/live-profile-reload.md` — live-only, referenced by the SKILL body's reload-direction section, so the tree's two-way gate (a body that names a `references/<file>.md` not in the tree) reds until it is committed.
- `references/reload-authority.md` — live-only reference file, versioned for gate symmetry.

Not part of this drift (confirmed byte-identical live↔tree by the planner): `references/agent-profile-tree-review.md` and `references/local-verification.md` — untouched.

Remedy applied as a byte-identical live→tree versioning PR per #791, with a change-note fragment per #1123. The #1193 load-bearing verdict wording is already on main (my own merged PR #1197) and is preserved unchanged.
