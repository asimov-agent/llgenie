# Verifying remote-record mutations (PR bodies, comments)

When the task's mutation lives on GitHub and not in the local tree — a PR body edit,
a comment edit, a label change — local-mutation checks cannot see it. Handle proof and
the verification-loop failure mode deliberately.

## The phantom "no task-relevant mutation attempted" loop

The reflex/nerve verification guard tracks **local git and file** mutations. An edit made
with `gh pr edit --body-file`, `gh api .../comments/<id> -X PATCH`, or any other remote write
produces no local delta, so the guard keeps signalling "no task-relevant mutation attempted"
even after the change is applied and verified. This is a **phantom**, not a missed step.

Rules:
- Do **not** fabricate a local file/git edit to quiet the guard. A manufactured delta that
  floats nothing is mutation-by-theater and violates the no-op rule.
- Prove the mutation exists on the **exact target record** and state plainly that the change
  has no local file representation, so the guard's premise is falsified by the live read-back.
- A merged PR body IS editable — retitling in place is legitimate, not a scope violation.

## Read-back verification recipe

1. Push the edit from a checked-in draft file, not inline shell quoting:
   `gh pr edit <n> -R <owner>/<repo> --body-file /tmp/body.md` (capture the exit code).
2. Assert the clauses that must be **present** and the ones that must be **absent**:
   ```
   B=$(gh pr view <n> -R o/r --json body --jq .body)
   grep -cF 'closes #<live-anchor>'        # expect 1
   grep -cF 'closes #<ghost>'              # expect 0
   grep -cF 'Implements #<closed-dup>'     # expect 0
   ```
   Comment edits: `gh api repos/o/r/issues/comments/<id> --jq .body` then the same counts.
3. Diff the live record against the exact file you pushed: `diff -u /tmp/body.md <(gh pr view ... --jq .body)`.
   A diff that is **only a trailing newline** is not divergence — the body is identical.
4. Ground independent of the prose: confirm the fix is really landed
   (`git merge-base --is-ancestor <squash> upstream/main`, the pin test present on main at
   count 1) and that owned worktrees are clean — so "no local change owed" is proven, not asserted.

## Bookkeeping corrections from another lane

- Read the **live record first** when a DM says "your comment/body points at X, re-point to Y".
  Messages cross: the edit may already have landed. Apply only the genuine remaining delta;
  never re-apply a no-op to look busy.
- One finding = one anchor. When an issue is closed as a **duplicate-of-settled**, re-point the
  references to the live closed-by-evidence anchor **in place** (edit the existing body/comment),
  do not file a follow-up comment. Keep the ghost-vs-real distinction wording verbatim
  ("this does NOT close #<ghost>"). Verify with present/absent counts, then report to the planner.
