# check-pr-closing: commit title vs body, and where the branch lives

## `make check-pr-closing` reads the COMMIT TITLE (squash text), not just the PR body

A body-only `closes #<n>` reds BOTH `scope` and `guard` with the
`check_pr_closing` gate exit 2. A commit titled `fix(x): …` whose BODY says
`closes #<n>`, or whose title is a bare summary with no close token, fails: the
gate requires the adjacent `(closes #<n>)` (or `fixes`/`resolves`) token in the
commit SUBJECT **and** the body.

Fix is a **message-only amend**:

1. `git commit --amend` the title to end `… (closes #<n>)`.
2. Confirm the tree is unchanged — `git diff --stat <old-sha> HEAD` must be empty.
3. Run `make check-pr-closing` and require rc 0 BEFORE pushing.
4. `git fetch` the remote immediately before the force, then
   `git push --force-with-lease --force-if-includes` (lease held old→new; report the
   forced update).

A plain `--force-with-lease=<ref>:<sha>` can fail on a refspec quirk; the
tracking-ref form after a just-fetched remote is the reliable one.

`closes #<n>` in the BODY is still required too — the two places must AGREE. A
body saying `Completes issue #<n>` without an adjacent `closes #<n>` is the same
red.

### Multi-commit branch: the gate JOINS every commit in the range, and `(issue #<n>)` is NOT a closing token

The squash text the gate checks is the JOINING of ALL commits in `origin/main..HEAD`,
not just HEAD. A branch of three commits whose subjects all end `(issue #<n>)` — or
`(#<n>)`, or a bare `#<n>` — closes NOTHING: the joined set is empty while the body
closes `#<n>`, so it reds with `the joined commit messages close none; the PR body
closes #<n> — those sets have to be the same`. The issue NUMBER appearing in a subject
is not a keyword; only `closes`/`fixes`/`resolves #<n>` counts, and it must be present
in the joined text.

- **Fix with a message-only amend, not a rewrite.** Append a `closes #<n>` line to one
  commit's BODY (`git commit --amend` on HEAD if HEAD is the natural carrier, or reword),
  confirm the tree is unchanged (`git diff --stat <old-sha> HEAD` empty), and re-run the
  gate locally before pushing.
- **Do NOT rewrite subject lines across the range with `git filter-branch --msg-filter` /
  `git rebase --exec` piping:** a `--msg-filter` whose command does a bare `cat` consumes
  stdin and DROPS the original subjects, leaving mangled messages that red harder. If
  subjects are already mangled, recover by rebuilding the branch cleanly from the
  merge-base — `git reset --hard <merge-base>` then re-`cherry-pick` the original commits
  (whose subjects survive in the object store) — and only then append the closing line.
- **Verify the joined set explicitly:** `git log --format='%b' origin/main..HEAD | grep -i
  'closes #<n>'` must print a line, and `python3 scripts/check_pr_closing.py check
  --body-file <f> --head <branch> --base origin/main --rev HEAD` must exit 0.
- **Pass `--base origin/main`, never `--base main`.** A bare `main` resolves to a local ref that
  can point at a stale or unfetched tip, pulling the whole history into the range and joining
  commits that are not yours — a false red that says the sets disagree when they do not. Fetch
  `+refs/heads/main:refs/remotes/origin/main` first, then re-run with `--base origin/main`; a red
  that disappears under the correct base was the base arg, not your commit messages.

## The branch may live on the `fork` remote (`andyholst/llgenie`), not `origin`

A `git branch -a` / worktree search that only looks at `origin` finds nothing.
`gh pr view <n> --json headRepository,headRefName` names the owning remote.
`git fetch fork <branch>` then create the worktree — otherwise the local
checkout is detached or absent. Do NOT conclude a branch is missing until both
remotes are checked.

### Pushing the same head to BOTH remotes: each lease is per-remote

When the branch exists on `origin` and `fork`, a force-push must satisfy a lease at each, and the
two are independent: pushing to `origin` first leaves the fork's remote ref at the OLD sha, so a
`--force-with-lease=<branch>:<new-sha>` computed once for both is rejected on the fork. Push each
remote separately, reading its own current ref first:

```bash
git ls-remote fork refs/heads/<branch>          # the fork's real lease value
gh api repos/<owner>/<repo>/git/refs/heads/<branch> --jq .object.sha
git push fork <branch> --force-with-lease=<branch>:<fork-old-sha>
```

A rejected lease is the guard working, not an auth problem — re-read that remote's sha and retry
once. Verify the finished state by comparing all three (local `rev-parse HEAD`, each remote's
`ls-remote`, and the PR's `headRefOid`) before reporting the head.

### `gh pr create --head <branch>` fails with `No commits between main and <branch>`

Because the branch lives on the `fork` remote, an UNQUALIFIED head makes GitHub look for that branch
in the BASE repo and find nothing:

```
pull request create failed: GraphQL: Head sha can't be blank, Base sha can't be blank,
No commits between main and <branch>, Head ref must be a branch
```

That is a wrong-repo context, NOT an unpushed commit and NOT a missing branch. Qualify the head with
the fork owner:

```bash
gh pr create --repo asimov-agent/llgenie \
  --head andyholst:<branch> --base main \
  --title '<title>' --body-file <file>
```

Sanity-check the push landed first (`git ls-remote https://github.com/andyholst/llgenie.git
refs/heads/<branch>` equals your local `git rev-parse HEAD`) and then re-issue with the owner prefix
— do not re-push, and do not read the error as a stale/missing branch.

## A closing keyword in PROSE closes that number too

`check_pr_closing` scans the ENTIRE PR body text, not just a dedicated closing
line. A sentence that describes another ticket's fixture or example — "the new
check reproduces the `closes #<m>` shape" — silently adds `#<m>` to the
body-closing set, and the gate reds with a set mismatch (`the body closes #<m>`)
against a commit range that legitimately closes only `#<n>`.

- Before pushing, grep the body for EVERY closing token (case-insensitive
  `clos|fix|resol… #<num>`) and confirm each is one you mean to close.
- Describe a foreign issue as `issue #<m>` or `the #<m> fixture` — never with a
  closing keyword.
- Fix it with a BODY edit (`gh pr edit <n> --body-file f`), never a commit
  rewrite; the commit range was never the problem.

## The bot-authored PR body also needs `AGENTS:` and `BASE:` lines

A body that closes the issue correctly can still red `scope` for missing
structural lines the PR-hygiene/author gates parse:

- `AGENTS:` — the census line (base sha, file count, line count) the author gate
  expects on a bot-authored PR.
- `BASE:` — the base branch name; its absence reds even when `--base main` was
  passed to `gh pr create` (the line, not the flag, is what the gate reads).

Craft the body into a file, pass `--body-file`, then read it back
(`gh pr view <n> --json body`) and assert all three survive: an `AGENTS:` line, a
`BASE:` line, and exactly one intended `closes #<n>`.

## Re-authoring a MULTI-commit range (the author gate)

`check-pr-authors` requires every commit in `origin/main..HEAD` be authored by the
allowlist (`Asimov Agent <support@docondee.com>` / the owner's address).
`git rebase --reset-author` and `git commit --amend --author` do NOT reliably
re-author a whole range — `--reset-author` uses whatever author is "current"
(a repo-local `user.name` or inherited env), so a rebase that reports success can
leave every commit on the bot name. Rewrite the range deterministically:

```bash
git filter-branch -f --env-filter 'export GIT_AUTHOR_NAME="Asimov Agent";
  export GIT_AUTHOR_EMAIL="support@docondee.com"; export GIT_COMMITTER_NAME="Asimov Agent";
  export GIT_COMMITTER_EMAIL="support@docondee.com";' -- origin/main..HEAD
```

Then verify `git log --format='%ae | %an' origin/main..HEAD` shows ONLY the
allowlisted identity, `git diff --stat <old-head> HEAD` is empty (tree unchanged),
and clean the backup ref (`git update-ref -d refs/original/refs/heads/<branch>`) —
then force-push your own unmerged branch with the lease pinned to the head the PR
currently shows.

## Emissions: do not claim "all checks green" from a filtered grep

`gh pr checks <n> --json name,state | grep -v SUCCESS` returning empty can mean
checks are not yet CREATED (a fresh head), not that they passed. Always count
states explicitly (`grep -oE '"state":"[A-Z_]+"' | sort | uniq -c`) and report
IN_PROGRESS legs as outstanding before claiming green.
