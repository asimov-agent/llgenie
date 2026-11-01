# Versioning the tester lane's fold tool (2026-11-01) (issue #1079)

The tester lane's live profile carries a Python tool, `fold-live-profile.py`, that this lane's own
SKILL.md and `agent-profile-versioning.md` reference as the canonical way to enumerate the lane's
files and copy live drift back into the tree. It exists **only** in the live profile
(`~/.hermes/profiles/llgenie-tester/skills/llgenie-pr-testing/scripts/`) — it was never versioned in
the repo, so the tree's own tools referenced a utility that did not exist here. That is the exact
`absent-from-tree` class: a live-authored lane tool with no reviewable counterpart.

## What it does

- Derives the lane's file set from the **TREE** (`git ls-files agents/<profile>`), never an assumed
  directory shape — the rule §11 was encoding.
- Reports a two-way table: tree-vs-live per tracked file, plus `LIVE-ONLY` files (a path the live
  home has that the tree does not) and mid-write detection (hash twice, pause; a movement between
  reads is another lane's active edit → exit 2, refuse a blind copy).
- `--copy` writes drifted live files into the tree with `shutil.copyfile` (bytes only) then re-hashes
  the destination to prove the copy landed.
- Exit codes: 0 no drift (or copy done), 1 drift under `--check`, 2 mid-write / missing lane.

## Where it lives

Repo-root `scripts/fold-live-profile.py`, sibling to the other profile-seam tools (`agent_profile_sync.py`,
`check_agent_profiles.py`) and callable by its full path from any worktree. The live profile keeps its
copy; this versioning makes it reviewable and gateable.

## Census impact

`scripts/` count rises (130 → 131); the change re-measures `check_architecture_census.py` **at the new
committed head**, so the `measured at` pointer and the `scripts/` figure move together in this PR.
Verified `py_compile` clean on the copied tool.
