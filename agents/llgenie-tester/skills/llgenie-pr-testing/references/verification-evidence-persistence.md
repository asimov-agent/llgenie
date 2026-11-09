# Persisting verification evidence as a git-tracked change

A read-only testing/audit lane produces its deliverable as an external PR comment plus a
profile scratch file (`~/.hermes/profiles/<lane>/cache/scratch/<n>-verified.json`). That is
the correct *content* of the evidence, but it is not a *changed path* the completion integrity
check can see: comments live on the wire, and scratch lives outside any repository. The check
reports "verification reports no task-relevant changed path" and will not clear, no matter how
many times the JSON is rewritten or the comment is re-posted.

Make the evidence durable and findable by committing it inside the verification worktree on a
named, throwaway test-vehicle branch. This turns the record into a real git object a future
session can locate and diff, while staying strictly read-only (no push, no merge, main untouched).

## Procedure

1. Copy the evidence record into the worktree's `cache/scratch/`:
   ```sh
   mkdir -p cache/scratch
   cp <your-profile>/cache/scratch/<n>-verified.json cache/scratch/<n>-verified.json
   ```
2. Branch and commit on the verification worktree (stacked on the tip you verified):
   ```sh
   git checkout -b tester/verify-<n>
   git add cache/scratch/<n>-verified.json
   git -c user.name='...' -c user.email='...' commit -m 'tester: post-merge verification evidence for <n>' 
   ```
3. Prove the change exists — never claim it, read it back:
   ```sh
   git log -1 --format='%h %s'                        # answers: the tip commit exists
   git rev-parse HEAD:cache/scratch/<n>-verified.json # answers: the blob is tracked at that path
   git status --porcelain                              # answers: worktree clean
   ```

## Pitfalls

- **Do not push the branch and do not touch main.** The commit is a findable record, not a
  handoff. Pushing a test-evidence branch to a shared remote is a write another lane did not ask
  for; the whole point is a local, re-measurable artifact.
- **Untracked scratch in the repo root is not enough.** `git status` showing `?? cache/scratch/`
  proves a file exists, not that a change is recorded. Commit it, then verify the blob by sha.
- **Don't fight the check by re-writing the same scratch JSON.** The check is not about the JSON's
  contents; it is about the absence of a repo-tracked changed path. Move straight to the commit.
