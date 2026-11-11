# Repo workflow pitfalls (before the code, after the push)

Depth for llgenie work that is not engine-image specific: finding half-finished work, the remote layout, the
OpenSpec mechanics, and reading CI state. SKILL.md is at its size cap, so this lives here.

## Start here: is this work already half-done?

The repo has dozens of agent worktrees and long-lived bot branches, so an issue you are about to implement is
often already implemented on a branch whose PR was closed — a rebase conflict, a red gate, a superseded run.
Sweep before writing code; reviving a branch onto `origin/main` is far cheaper than re-deriving it:

```bash
ls ../llgenie-wt/                                   # prior agent worktrees, named by topic
git branch -a | grep -i <topic>
gh pr list --repo asimov-agent/llgenie --state all --search "<topic> in:title" --limit 20
gh pr view <n> --json state,closedAt,comments --jq '.state, .closedAt'
```

A closed PR whose comments carry `rebase-bot … gave-up` means the implementation is good and only the conflict
resolution is owed: reuse its worktree (one branch = one worktree), `git rebase origin/main`, resolve by hand.
When several branches carry the same change, keep the best and drop the rest instead of merging them.

`gh pr list --state all --head <branch>` only finds the PR while the branch still exists; search by title once
the branch is gone.

**A stale local checkout lies about `main`.** `git status` reporting `main … behind N` means grepping the user's
checkout reads files that no longer match the remote — this is how a "fixed" job gets re-diagnosed from old
text. Read the real tree with `git show origin/main:<path>`, cut the worktree from `origin/main`, and re-verify
any file you quoted before you knew the checkout was stale.

## Remotes are inverted in the standard clone

`origin` is `asimov-agent/llgenie` (UPSTREAM); `fork` is `andyholst/llgenie`. So `git push -u origin <branch>`
publishes the branch to the upstream repo, which is not the shape the PR rule wants. Push to the fork and open
the PR from the fork head:

```bash
git push -u fork <type>/<kebab>
gh pr create --repo asimov-agent/llgenie --base main --head andyholst:<type>/<kebab> --title … -F body.md
git push origin --delete <branch>     # only when the branch was already pushed to origin by mistake
```

## OpenSpec mechanics that bite before any code exists

- `make openspec-new NAME=<kebab>` runs the container as **root**, so the change directory it creates is
  root-owned and `write_file` into it fails with `Permission denied`. Chown it first:
  `sudo chown -R "$(id -u):$(id -g)" openspec/changes/<kebab>`
- `make ci-openspec` runs `openspec-tasks-check`, which **fails on any unticked `- [ ]`**. Never write a task
  whose truth only arrives after the merge (the post-merge proof, the next run, the reviewer's action): tick
  every box the branch can verify now, and record post-merge acceptance evidence in the PR body and
  `agent-wiki/` instead.
- A scenario needs its `- **Test:**` line, and the test body needs `# Given / # When / # Then` markers as
  separate blocks (blank line between them) — the suite's own checks read that shape.
- Keep the issue, the OpenSpec change and the PR describing the SAME objective. When the fix narrows while you
  implement it, edit `proposal.md`/`spec.md`/`tasks.md` AND the issue body in the same commit batch.
- `make openspec-validate NAME=<kebab>` before any "done" claim; a red `ci-openspec` is usually the unticked-box
  check, not the spec.

## Reading CI state without the table

`gh pr checks` prints a table whose columns shift with terminal width, so `awk '{print $2}'` reports nonsense
counts. Parse JSON:

```bash
gh pr checks <n> --repo <slug> --json name,state,bucket \
  --jq 'group_by(.bucket)[] | "\(.[0].bucket): \(length)"'
gh pr checks <n> --repo <slug> --json name,state --jq '.[] | select(.state=="FAILURE") | .name'
```

`no checks reported on the '<branch>' branch` for a just-pushed head means the run has not registered its jobs
yet — confirm with `gh run list --branch <branch>` before treating it as a failure. A whole CI run takes ~50
minutes here (engine images dominate), so poll with `sleep 300` between checks, never one call per job.
