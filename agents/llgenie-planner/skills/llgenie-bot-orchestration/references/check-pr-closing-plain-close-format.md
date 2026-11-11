# check-pr-closing: the close must be PLAIN, in BOTH texts, and the two sets must match

`closes **#N**` (markdown bold) is NOT a close. `check_pr_closing.py` reads the PR body with
`\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+#(\d+)` — a `**`, `:`, comma, or any non-space
between the keyword and `#N` MISSES the match. Measured on #1328, which left #1327 open: the
markdown wrapper is a real silent failure.

A PR that implements an issue must:
1. carry the PLAIN literal `closes #N` (no `**`, no colon) in the body;
2. carry the same adjacent close in the SQUASH/commit messages — this repo
   `squash_merge_commit_message=COMMIT_MESSAGES`, so the commit that lands on main is the joined
   branch commit messages, NOT the PR body;
3. have body-close set == commit-close set — a mismatch (commits close #N, body closes none, or
   vice versa) is its own `check-pr-closing` violation.

An `Issue: #N` line or a title ending `(#N)` is a CLAIM; each claim must be an adjacent close in
both texts. A `#N` that is prose-only is not a claim. Failure text to grep for:
`[check-pr-closing]`, "the PR body does not adjacently close a claimed issue", "the squash commit
text and the PR body close different issues".

Guard: before opening/updating any PR that implements an issue, write the body with the exact
plain `closes #N` line, and make the first commit message carry the same close — never edit a
close into bold, never let the body lose the plain line after a body-only edit (body edits do not
re-trigger CI; a body-only rewrite that drops/breaks the plain line reds check-pr-closing on the
STALE head run with no fresh run to clear it).
