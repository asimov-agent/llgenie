# Worktree base seam (agent-implemented changes)

When an agent implements an issue and opens a PR, work starts in its OWN worktree
cut from the **freshly fetched** `origin/master`, and the base is **verified, never
assumed**. This is the shape those changes take.

## The three verbs (one implementation, `scripts/worktree_base.py`)

- **check** — prove this checkout IS the fetched tip. A CI job that cuts a branch
  runs it first and refuses to cut anything on a stale checkout. The checkout is
  only `origin/master` by accident, so a fresh clone is not a substitute.
- **new** — create a NEW branch at the fetched tip in its own worktree
  (`../<repo>-wt/<kebab>` by default, `--in-place` for a runner that must write in
  place). Refuses: an existing branch (never re-cut — discard), a worktree inside
  the repo (a later `git add -A` would commit the sibling tree), the base branch
  itself as a target.
- **resume** — fetch the branch FIRST, then reuse its worktree. Refuses to reset a
  branch carrying commits not on `origin` (`-B` throws them away), and reports
  `behind_base=` so drifting work is re-based before push.

Every path proves the caller's HEAD, branch and local `master` are untouched.

## Makefile shape

Host targets (`base-check`, `worktree-new BRANCH=… [IN_PLACE=1]`, `worktree-resume
BRANCH=…`): git and its credentials live on the runner, not in a container that
would write into the shared `.git`. Pipelines call the Makefile targets, never a
bare `git checkout` in YAML.

## Test pattern (real git, no mocks, rule "the test IS the contract")

Drive the REAL script against REAL repositories — seed a clone that fetched
exactly ONE ref (the `actions/checkout` + `ref: master` shape) and reproduce the
resume path against it; the failure mode is `pathspec '<branch>' did not match
any file(s) known to git`, which ONLY appears in a one-ref clone.

## Pitfalls

- **If work ever lands in the caller's clone instead of a worktree (the seam was
  not used), PUT IT BACK before finishing** — the user's checkout must end on the
  branch they left there, its working tree clean, with the merged work fetched
  (`git checkout <their-branch> && git merge --ff-only origin/master`). A session
  that moves the caller's branch and leaves it there is indistinguishable from
  one that broke their checkout; the first thing to fix when you notice is your
  own mess, then the branch it created.
- The seam must never `git checkout` the base branch and never switch any branch
  the caller stands on — the worktree is created from the remote-tracking ref,
  the caller's HEAD/branch/local `master` are untouched (asserted by the tests).

- `git checkout <branch>` fails in a one-ref clone (
  `pathspec … did not match any file(s) known to git`) even when `ls-remote` shows
the branch on `origin` — so a resume must FETCH the branch before checking it out,
and must never reset it with `-B` (a branch with commits not on `origin` is
destroyed).
- A workflow test that greps the YAML for marker words stays green over a dead
path — assert the executable seam (`make worktree-new` / `worktree-resume` /
`base-check` present, bare `git checkout` absent) AND run the real script against
a real repo, or a renamed/broken seam ships silently green.
- Pin the AGENTS.md rule's own wording in the test suite too, so a dev softening
it is caught, not silently tolerated.
- Resolving a rebase conflict with `git checkout --theirs -- <file>` (or
  `--ours`) on a WHOLE file silently reverts the OTHER side's newer content —
  it replaces the entire file, not just the conflicted hunks, so work that
  landed on `main` after your branch point is dropped and the PR ships a
  regression. Resolve conflicts surgically (edit the conflicted file, `git add`,
  `git rebase --continue`); never blanket-checkout a whole file during a rebase.
- A change that edits `.github/workflows/**` needs a token with the `workflow`
scope, or the push is rejected (`refusing to allow a Personal Access Token to
create or update workflow …`, both a local push and a bot's PAT).
