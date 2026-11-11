# Duplicate anchors, and editing a merged PR body

## One finding, one anchor

Before accepting a lane's freshly filed anchor issue, search the board for one already filed
for the same finding — open, or **closed by merged evidence**. When two anchors exist, close the
newer as *duplicate-of-settled*, naming the merged squash sha and the surviving anchor, and say in
the close comment that the diagnosis was not rejected — the finding is COMPLETE at the older anchor.

A duplicate that carries `agent:implement` is worse than dangling: it will dispatch a bot to
re-implement already-merged code and open a second vehicle for a completed finding. Close it
even if its six-section body is better written than the original.

Then **re-point the merged PR** so its record references the live anchor, not the closed duplicate.

## A merged PR body is editable; only the closing link is frozen

- `gh pr edit <n> --body ...` works on MERGED pull requests. "The body is frozen because it merged"
is a false premise a lane will assert; correct it and ask for the retitle.
- What is frozen is the *closing keyword*: `closes #X` was consumed at merge time, so adding
`closes #Y` afterwards closes nothing. Use `Implements #<anchor>` plus a note instead.
- The edit belongs to the lane that owns the PR's record. Ask; do not edit another lane's PR body
yourself.
- Verify by read-back of the exact line (`gh pr view <n> --json body | grep -nE 'closes|Implements'`).

## Pitfall: shell substitution in a close comment

`gh issue close <n> --comment "...$(git grep -c ...)..."` overran the argument list
(`Argument list too long`) and silently left the issue OPEN — exit 0 was tail-piped away.
Write the measured value as a literal (e.g. "pin test present on main, count 1") and always
re-read the issue state afterwards to confirm the close landed.
