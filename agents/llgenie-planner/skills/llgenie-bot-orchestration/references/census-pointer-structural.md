# The census `measured at` pointer: structurally unserializable for file-adding PRs (2026-10-30)

The `check-architecture-census` gate compares `docs/ARCHITECTURE.md`'s stated counts + `measured at <sha>` against the tree. Two distinct failure modes appeared in one night:

1. **Dangling pointer** — the `measured at` sha is not a commit object at all (`348f7b4e`, `bc3859b` after a squash). Fixed by pointing at a *real* commit.
2. **Real-but-not-ancestor pointer** — the sha is a real commit reachable from the PR head, passes the gate *today*, but is **not an ancestor of main** → it dangles the instant the PR squash-merges → main's `check-docs` re-reds on merge (the `d9239ab`/`0471685` cases). Same class as (1), deferred one merge.

## The structural root (why per-PR pointer chasing CANNOT work)

A **file-adding PR can never have a `measured at` sha that is simultaneously (a) a real commit whose tree count matches the PR head and (b) an ancestor of main** — because the files the PR adds do not exist on main until the PR merges. There is no such sha to pick. So every file-adding PR that rewrites the census pointer will *either* under-count (point at pre-add main state → gate reds on the PR) *or* dangle post-squash (point at a branch commit → main reds on merge).

**Consequence for the planner:** when a red is "census measured-at", do **not** dispatch N per-PR pointer fixes across the rebase/engine/tester lanes — they will collide (double vehicles on one branch) and none can be made squash-safe. The fix is the **gate class** (llgenie #1053: referent = tree at the named sha, tolerating the file-adding case), filed once and fixed at the source. Hold the affected PRs' *merges* until the gate fix lands, then re-derive each once.

**Invariant to state to a lane:** "pointer is a real commit" is insufficient; the usable shape is a sha that stays reachable from main *after* the squash — which for a file-adding PR means: don't chase it, land the gate fix (#1053) first.

## Resolution: referent-ancestor semantics (landed — supersedes the per-PR chase)

The gate now compares the doc's counts against the tree **at the named referent** and requires only that the referent is an **ancestor of HEAD**. Three consequences every lane should apply without re-deriving:

- **The census block describes the tree at the pointer, not at HEAD.** Drift between the pointer's tree and HEAD's tree is expected and legal; a doc whose counts are lower than the current tree count is correct, not stale.
- **A file-adding PR needs no census edit at all.** Leave the block alone — the existing pointer stays an ancestor and its counts stay true about the tree it names. Verified live on a branch that added a whole new top-level tree and rebased twice without touching the census.
- **When `docs/ARCHITECTURE.md` conflicts during a rebase, keep main's block**, not the branch's larger re-derived numbers. Re-deriving per-branch counts was the pre-fix habit and is now the *wrong* answer; telling a lane to "keep your own bigger numbers" is a planner error that makes a clean rebase look like a conflict source.

Verify by quoting the gate's own line, which prints the referent, the counts and the ancestor check together — do not hand-recount.
