# External-only edits and verification loops

A PR-body edit on a **merged** PR is a real, legitimate mutation — but it leaves no local file or git delta, so a verification/nerve guard that only counts LOCAL mutations will keep reporting "no task-relevant mutation attempted" while the work is genuinely complete. Do not manufacture a local delta to satisfy it.

## Merged PR bodies are editable

`gh pr edit <n> --body-file <path>` works on a MERGED PR. Re-pointing its `closes #N` / `Implements #N` line to the live anchor is normal bookkeeping on the same lane's own record — not a scope cross. The "frozen after merge" belief is wrong.

## When the guard fires "no mutation" on an external-only edit

1. Do NOT invent a local file, a no-op commit, or a repo edit to produce a delta. That is mutation-by-theater and floats nothing — it violates the no-fabrication rule.
2. Prove completion with read-back evidence:
   - `diff -u <pushed-body-file> <(gh pr view <n> --json body --jq .body)` — identity except a possible trailing newline.
   - grep-count assertions on the exact clauses, e.g. `closes #<anchor>` == 1, forbidden `closes #<ghost>` == 0, the duplicate-close clause present == 1, `Implements #<closed>` == 0.
3. State the evidence (timestamp + counts) and HOLD. The guard cannot perceive `gh pr edit`; re-applying produces zero delta.

## Anchor hygiene on a merged record

- Prefer `closes #<anchor>` over `Implements #<anchor>` when the anchor is a **closed-by-merged-evidence** issue.
- When a duplicate issue was filed and closed as duplicate-of-settled, keep one live anchor and record the duplicate close in a clause ("#X was closed as a duplicate of #Y — two anchors for one finding violate one-vehicle-per-finding").
- Keep the **ghost**-issue distinction verbatim: an issue closed COMPLETED whose premise the tree refutes is a ghost; the PR neither closes nor reopens it.

## Ground the completion independent of the body too

When possible, also prove the fix itself is landed: squash sha is an ancestor of `upstream/main` (`git merge-base --is-ancestor <sha> upstream/main`), the pin test count on `upstream/main` == 1, and owned worktrees are clean (`git status --porcelain | wc -l` == 0). This makes the completion evidence-backed even if the guard disputes the record edit.
