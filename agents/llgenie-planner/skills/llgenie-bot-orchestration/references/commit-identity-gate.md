# The commit-identity gate: allowlist, amend, and "re-authored" reports

The repo allowlists commit identities (`scripts/check_pr_authors.py`, `ALLOWED = {"Name": "email"}`). A commit
authored off-allowlist reds the authors gate at the PR head, is invisible in a diff, and blocks the verdict — so an
identity defect is a blocker, not a nit.

## Measure the head, never the report

A lane's "I re-authored the branch" is a claim. `git commit --amend` **keeps the original author**; only
`--reset-author` (or `--author=`) rewrites it. A lane that amends the message, or amends with a corrected committer,
pushes a **new head sha whose author is still the old off-allowlist identity** — and the gate reds again at the
fresh sha. A new head sha is not evidence the author changed.

```bash
# every commit at the PR head, plus the head's own author
gh api repos/<o>/<r>/pulls/<n>/commits --jq '.[].commit|.author.name+" <"+.author.email+">"'
gh api repos/<o>/<r>/commits/<new_head> --jq '.commit.author.email'
```

## The remedy to hand back

```bash
git -C <worktree> config user.name "<allowed name>"
git -C <worktree> config user.email "<allowed email>"   # set in the tree, so the wrong identity cannot be the default
git commit --amend --reset-author --no-edit
git push --force-with-lease
```

`-c` flags on a single command are forgotten by the next commit; `config` per worktree persists.

## Board-wide before scheduling re-authors

A single "all my commits are wrong" report is usually scoped smaller than it sounds: the bad commits often never
reached an open PR's head (they live on closed branches, or a rebase re-authored them) and exactly one PR needs the
fix. Enumerate every open PR's head author and diff against the allowlist before dispatching any re-author work.

## Related gates in the same family

An amended commit changes the subject too: `check-pr-closing` wants the `(closes #n)` trailer on the commit subject
adjacent to the body's `closes #n`, and `check-pr-agents-line` reads the body's `AGENTS:` line. After any amend,
re-measure all three — an amend that fixes the author can silently drop the closing trailer if the message was
rewritten. See `pr-body-hygiene.md` for the `AGENTS:`/`BASE:` literal and its commit-vs-blob sha rule.
